function scrollToSection(id){
  const el = document.getElementById(id);
  if(el) el.scrollIntoView({ behavior: 'smooth' });
}

/* Feature carousel (4-at-a-time) */
(function(){
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
      d.addEventListener('click', () => {
        setIndex(i);
      });
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
    const newVisible = getVisibleCount();
    visible = newVisible;
    maxIndex = Math.max(0, totalSlides - visible);
    index = Math.min(index, maxIndex);
    buildDots();
    setIndex(index);
  });

  buildDots();
  setIndex(0);
  start();
})();

/* Feature wheel */
(function(){
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
})();