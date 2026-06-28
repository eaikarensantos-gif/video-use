# HyperFrames Animation Reference

## Why seekability matters

HyperFrames renders by scrubbing the composition frame-by-frame in headless Chrome. If an animation runs on wall-clock time (`setTimeout`, `Date.now()`, `requestAnimationFrame` with no seek support), the rendered frames will not match what you see in preview. Always use a seekable animation model.

## GSAP timelines (recommended)

GSAP timelines are the most natural fit — they support `.seek(t)` natively.

### Wiring to HyperFrames

```html
<script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.5/gsap.min.js"></script>
<script>
  gsap.defaults({ ease: "power2.out" });

  document.addEventListener('DOMContentLoaded', () => {
    const tl = gsap.timeline({ paused: true });

    tl.from('#headline', { opacity: 0, y: 40, duration: 0.6 })
      .from('#subline',  { opacity: 0, y: 20, duration: 0.5 }, '-=0.2')
      .from('#cta',      { opacity: 0, scale: 0.9, duration: 0.4 }, '+=0.3');

    // HyperFrames sets window.__hf_play before DOMContentLoaded fires.
    // If present, hand the timeline over; otherwise play normally (preview mode).
    if (typeof window.__hf_play === 'function') {
      window.__hf_play(tl);
    } else {
      tl.play();
    }
  });
</script>
```

### GSAP easing cheat sheet

| Ease | Use case |
|------|----------|
| `power2.out` | Single element reveal (default) |
| `power2.inOut` | Continuous motion between states |
| `power3.out` | Punchy entrance, fast deceleration |
| `elastic.out(1, 0.5)` | Playful bounce (use sparingly) |
| `back.out(1.7)` | Slight overshoot, then settle |
| `none` / `linear` | Never use for visual elements |

### Common timeline patterns

```js
// Staggered list reveal
tl.from('.list-item', { opacity: 0, x: -30, duration: 0.4, stagger: 0.1 });

// Counter number animation
const obj = { val: 0 };
tl.to(obj, {
  val: 9800,
  duration: 2,
  ease: 'power1.inOut',
  onUpdate: () => {
    document.querySelector('#counter').textContent =
      Math.round(obj.val).toLocaleString();
  }
});

// Typewriter (character-by-character)
// Split text into spans first, then stagger opacity
tl.from('.char', { opacity: 0, duration: 0.03, stagger: 0.04 });

// Highlight underline draw
tl.from('#underline', { scaleX: 0, transformOrigin: 'left center', duration: 0.5 });

// Card flip
tl.to('#card', { rotateY: 180, duration: 0.8, ease: 'power2.inOut' });
```

### ScrollTrigger in HyperFrames

Do NOT use ScrollTrigger — HyperFrames doesn't scroll. Use timeline labels and `tl.addLabel()` instead of scroll positions.

## CSS animations (auto-adapted)

HyperFrames pauses and seeks `document.timeline` automatically for CSS animations. Author them normally:

```css
@keyframes fadeUp {
  from { opacity: 0; transform: translateY(30px); }
  to   { opacity: 1; transform: translateY(0); }
}

.headline {
  animation: fadeUp 0.6s cubic-bezier(0.33, 1, 0.68, 1) both;
  animation-delay: 0.2s;
}
```

Rules:
- Use `animation-fill-mode: both` (or `forwards`) so elements hold their final state.
- Prefer `cubic-bezier` easing over `ease-in-out` keyword for precision.
- Avoid `animation-iteration-count: infinite` — renders produce a fixed-duration output.

## Lottie (JSON vector animation)

```html
<script src="https://cdnjs.cloudflare.com/ajax/libs/lottie-web/5.12.2/lottie.min.js"></script>
<script>
  document.addEventListener('DOMContentLoaded', () => {
    const anim = lottie.loadAnimation({
      container: document.getElementById('lottie-container'),
      renderer: 'svg',
      loop: false,
      autoplay: false,
      path: './animation.json'
    });

    // Expose for HyperFrames seek
    window.__hf_lottie = anim;

    if (typeof window.__hf_play !== 'function') {
      anim.play(); // preview fallback
    }
  });
</script>
```

HyperFrames uses `window.__hf_lottie` to call `goToAndStop(frame, true)` during scrubbing.

## Three.js / custom adapter (HFAdapter interface)

For custom render loops, implement the `HFAdapter` interface:

```js
window.__hf_adapter = {
  // Called once before rendering starts
  init() { /* set up scene, camera, renderer */ },

  // Called for each frame during render; t is seconds from composition start
  seek(t) {
    // position your animation at time t
    // e.g. update uniforms, rotate objects, etc.
    renderer.render(scene, camera);
  },

  // Called to render a preview frame (non-seek mode)
  play() { /* start animation loop */ }
};
```

## Anime.js

```js
import anime from 'https://cdn.jsdelivr.net/npm/animejs@3.2.1/lib/anime.es.js';

const anim = anime({
  targets: '#box',
  translateX: 300,
  duration: 1000,
  easing: 'easeOutCubic',
  autoplay: false
});

window.__hf_play = (/* hf control */) => {
  // HyperFrames will manage seek via anim.seek(ms)
  window.__hf_anime = anim;
};
```

Expose via `window.__hf_anime`; HyperFrames calls `.seek(ms)` during frame capture.

## Web Animations API (WAAPI)

```js
const el = document.getElementById('box');
const anim = el.animate(
  [{ opacity: 0, transform: 'translateY(20px)' },
   { opacity: 1, transform: 'translateY(0)' }],
  { duration: 600, easing: 'cubic-bezier(0.33,1,0.68,1)', fill: 'both' }
);
anim.pause();

window.__hf_waapi = [anim]; // array of all Animation objects
```

HyperFrames calls `.currentTime = ms` on each listed WAAPI animation during scrubbing.

## Timing rules

- **Hold final frame ≥ 1s** before composition end. The viewer needs to read it; the edit needs a clean cut point.
- **Never parallel-reveal two elements.** Complete one entrance, then start the next.
- **Audio payoff sync:** if there's a spoken word that the animation should land on, start the reveal `reveal_duration` seconds earlier so the animation's hold frame coincides with the payoff word.
- **Over narration:** total composition duration ≥ narration audio length + 1s.

## Debugging frame accuracy

If rendered frames look wrong (wrong state for the timestamp), check:
1. Is the animation seekable? Replace `setTimeout`/`setInterval` with GSAP or WAAPI.
2. Is `window.__hf_play` wired correctly? Log it in DOMContentLoaded.
3. Run `npx --yes hyperframes validate .` — it reports non-seekable patterns.
4. Preview with `npx --yes hyperframes preview .` and scrub manually to spot issues.
