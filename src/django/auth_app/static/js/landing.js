$(document).ready(function() {

  initFeatureCarousel();
  initFeatureWheel();
  initFeaturesDropdown();
  initMobileNav();
  
});

function scrollToSection(id){
  const el = document.getElementById(id);
  if(el) el.scrollIntoView({ behavior: 'smooth' });
}

/* Feature carousel (4-at-a-time) */
function initFeatureCarousel(){
  const track = document.getElementById('featureTrack');
  const dotsWrap = document.getElementById('featureDots');
  if(!track || !dotsWrap) return;

  const slides = Array.from(track.querySelectorAll('.feature-slide'));
  const totalSlides = slides.length;

  function getVisibleCount(){
    const w = window.innerWidth;
    if(w <= 520) return 1;
    if(w <= 900) return 2;
    return 4;
  }

  let visible = getVisibleCount();
  let maxIndex = Math.max(0, totalSlides - visible);
  let index = 0;
  let timer = null;

  function buildDots(){
    dotsWrap.innerHTML = "";
    visible = getVisibleCount();
    maxIndex = Math.max(0, totalSlides - visible);

    const dotCount = maxIndex + 1;

    for(let i = 0; i < dotCount; i++){
      const d = document.createElement('button');
      d.type = 'button';
      d.className = 'carousel-dot' + (i === index ? ' is-active' : '');
      d.setAttribute('aria-label', `Go to slide ${i + 1}`);
      d.addEventListener('click', () => setIndex(i));
      dotsWrap.appendChild(d);
    }
  }

  function updateDots(){
    const dots = Array.from(dotsWrap.querySelectorAll('.carousel-dot'));
    dots.forEach((d, i) => d.classList.toggle('is-active', i === index));
  }

  function setIndex(i){
    index = Math.max(0, Math.min(maxIndex, i));
    const pct = (100 / visible) * index;
    track.style.transform = `translateX(-${pct}%)`;
    updateDots();
  }

  function next(){
    index = (index >= maxIndex) ? 0 : index + 1;
    setIndex(index);
  }

  function start(){
    timer = setInterval(next, 2600);
  }

  window.addEventListener('resize', () => {
    visible = getVisibleCount();
    maxIndex = Math.max(0, totalSlides - visible);
    index = Math.min(index, maxIndex);
    buildDots();
    setIndex(index);
  });

  buildDots();
  setIndex(0);
  start();
}

/* Feature wheel */
function initFeatureWheel(){
  const wheel = document.querySelector('.wheel');
  if(!wheel) return;

  const items = Array.from(wheel.querySelectorAll('.wheel-item'));
  const descEl = document.getElementById('wheelDesc');

  const total = items.length;
  let index = 0;
  let timer = null;
  let userLocked = false;

  function positionItems(){
    const size = wheel.getBoundingClientRect().width;
    const radius = Math.max(110, (size / 2) - 34);

    items.forEach((btn, i) => {
      const angle = (i / total) * (Math.PI * 2) - Math.PI / 2;
      const x = Math.cos(angle) * radius;
      const y = Math.sin(angle) * radius;
      btn.style.transform =
        `translate(calc(-50% + ${x}px), calc(-50% + ${y}px))`;
    });
  }

  window.addEventListener('resize', positionItems);
  positionItems();

  function setActive(newIndex){
    index = (newIndex + total) % total;

    items.forEach((b, i) =>
      b.classList.toggle('is-active', i === index)
    );

    if(descEl){
      descEl.textContent = items[index].dataset.desc || '';
    }
  }

  function next(){
    setActive(index + 1);
  }

  function start(){
    if(!userLocked){
      timer = setInterval(next, 2400);
    }
  }

  function stop(){
    if(timer) clearInterval(timer);
    timer = null;
  }

  items.forEach((btn, i) => {
    btn.addEventListener('click', () => {
      userLocked = true;
      stop();
      setActive(i);
    });
  });

  const initial = items.findIndex(b => b.classList.contains('is-active'));
  setActive(initial >= 0 ? initial : 0);
  start();
}

function initFeaturesDropdown(){
  const btn = document.getElementById("featuresBtn");
  const panel = document.getElementById("featuresPanel");
  if (!btn || !panel) return;

  let isOpen = false;

  function openPanel() {
    panel.hidden = false;
    panel.classList.add("is-animating");

    panel.style.height = "0px";
    panel.style.opacity = "0";
    panel.style.transform = "translateY(-6px)";

    const target = panel.scrollHeight;

    requestAnimationFrame(() => {
      panel.style.transition = "height 220ms ease, opacity 180ms ease, transform 180ms ease";
      panel.style.height = target + "px";
      panel.style.opacity = "1";
      panel.style.transform = "translateY(0)";
    });

    panel.addEventListener("transitionend", function done(e) {
      if (e.propertyName !== "height") return;
      panel.style.transition = "";
      panel.style.height = "auto";
      panel.classList.remove("is-animating");
      panel.removeEventListener("transitionend", done);
    });

    btn.setAttribute("aria-expanded", "true");
    isOpen = true;
  }

  function closePanel() {
    panel.classList.add("is-animating");

    const start = panel.scrollHeight;
    panel.style.height = start + "px";

    requestAnimationFrame(() => {
      panel.style.transition = "height 200ms ease, opacity 160ms ease, transform 160ms ease";
      panel.style.height = "0px";
      panel.style.opacity = "0";
      panel.style.transform = "translateY(-6px)";
    });

    panel.addEventListener("transitionend", function done(e) {
      if (e.propertyName !== "height") return;
      panel.style.transition = "";
      panel.style.height = "";
      panel.style.opacity = "";
      panel.style.transform = "";
      panel.hidden = true;
      panel.classList.remove("is-animating");
      panel.removeEventListener("transitionend", done);
    });

    btn.setAttribute("aria-expanded", "false");
    isOpen = false;
  }

  btn.addEventListener("click", (e) => {
    e.stopPropagation();
    isOpen ? closePanel() : openPanel();
  });

  document.addEventListener("click", (e) => {
    if (!isOpen) return;
    if (btn.contains(e.target) || panel.contains(e.target)) return;
    closePanel();
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && isOpen) closePanel();
  });

  panel.addEventListener("click", (e) => {
    const link = e.target.closest("a");
    if (link) closePanel();
  });
}

// Mobile navigation toggle burger menu
function initMobileNav(){
  const header = document.querySelector(".nav");
  const toggle = document.getElementById("navToggle");
  const nav = document.getElementById("siteNav");

  if(!header || !toggle || !nav) return;

  const closeMenu = () => {
    header.classList.remove("is-open");
    toggle.setAttribute("aria-expanded", "false");
    toggle.setAttribute("aria-label", "Open menu");
  };

  const openMenu = () => {
    header.classList.add("is-open");
    toggle.setAttribute("aria-expanded", "true");
    toggle.setAttribute("aria-label", "Close menu");
  };

  toggle.addEventListener("click", (e) => {
    e.stopPropagation();
    const isOpen = header.classList.contains("is-open");
    isOpen ? closeMenu() : openMenu();
  });

  document.addEventListener("click", (e) => {
    if(!header.classList.contains("is-open")) return;
    if(!header.contains(e.target)) closeMenu();
  });

  nav.addEventListener("click", (e) => {
    const link = e.target.closest("a");
    if(link) closeMenu();
  });

  window.addEventListener("resize", () => {
    if(window.innerWidth > 900) closeMenu();
  });
}
