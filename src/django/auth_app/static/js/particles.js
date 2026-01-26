const canvas = document.getElementById("particles");
const ctx = canvas.getContext("2d");

function resize(){
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;
}
window.addEventListener("resize", resize);
resize();

const particles = Array.from({length:60}).map(()=>({
  x: Math.random()*canvas.width,
  y: Math.random()*canvas.height,
  vx: (Math.random()-0.5)*0.3,
  vy: (Math.random()-0.5)*0.3,
  r: Math.random()*2+1
}));

function draw(){
  ctx.clearRect(0,0,canvas.width,canvas.height);

  for(const p of particles){
    p.x+=p.vx; p.y+=p.vy;
    if(p.x<0||p.x>canvas.width) p.vx*=-1;
    if(p.y<0||p.y>canvas.height) p.vy*=-1;

    ctx.beginPath();
    ctx.arc(p.x,p.y,p.r,0,Math.PI*2);
    ctx.fillStyle="rgba(148,163,184,0.3)";
    ctx.fill();
  }

  requestAnimationFrame(draw);
}
draw();
