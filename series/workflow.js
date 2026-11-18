/* Animated receipts, ledgers and case slips; data and palette belong to each registered story. */
(() => {
  const K=window.KIT, M=window.MO;
  const paper='#fff6df', ink='#192e30';
  const curve=(t,at,len=.55)=>M.tw(t,at,len,'outC');
  function box(g,x,y,w,h,c,r=12){g.fillStyle=c;g.beginPath();g.roundRect(x,y,w,h,r);g.fill();}
  function word(g,s,x,y,size,c,mono=false,max=910){
    g.fillStyle=c;g.font='800 '+size+'px '+(mono?'Consolas,"Microsoft YaHei",monospace':'"Microsoft YaHei",sans-serif');
    g.textBaseline='middle';g.fillText(s,x,y,max);
  }
  function place(g,x,y,r,opacity,draw){g.save();g.translate(x,y);g.rotate(r);g.globalAlpha*=Math.max(0,Math.min(1,opacity));draw();g.restore();}
  function barcode(g,x,y,w,color){for(let i=0,p=0;p<w;i++){const n=[5,3,9,4,3,7][i%6];if(i%2===0)box(g,x+p,y,n,33,color,0);p+=n;}}
  function heading(g,sc,t){
    box(g,82,169,16,34,sc.palette[1],1);word(g,sc.topic,118,184,32,paper);barcode(g,827,169,155,sc.palette[1]);
    box(g,83,226,908,2,'#9ea995',0);
    sc.head.forEach((s,i)=>Array.from(s).forEach((ch,j)=>{
      const p=curve(t,.06+.13*i+.045*j,.37);
      place(g,79+j*103,323+i*132+45*(1-p),0,p,()=>word(g,ch,0,0,105,i?sc.palette[2]:paper));
    }));
  }
  function sheet(g,x,y,w,h,c){g.save();g.shadowColor='#00161670';g.shadowOffsetY=17;g.shadowBlur=21;box(g,x,y,w,h,c,10);g.restore();
    for(let i=18;i<w;i+=26)box(g,x+i,y+h-8,11,8,'#22313030',1);}
  function drawBars(g,sc,t,x,y,w,h){
    const F=sc.palette, specs={
      D:[1,20/230,210/230],C:[1,.67,.33],A:[.70,.70,.70],E:[.48,.68,.91],F:[.9,.45,.66],G:[.88,.94,.27]
    };
    const p=curve(t,.35,.95);
    if(sc.module==='D'){
      const heights=specs.D.map(v=>v*h*.76*p);
      heights.forEach((v,i)=>{const base=i===1?y+h-heights[0]:y+h-v;box(g,x+i*w/3,base,w*.22,Math.max(2,v),i===1?F[1]:F[2],4);});
    }else if(sc.module==='E'){
      for(let i=0;i<4;i++)place(g,x+w*.19*i,y+70-i*15,(i-1)*.09,p,()=>{sheet(g,0,0,w*.36,h*.68,i%2?F[1]:paper);box(g,23,31,w*.28,h*.25,F[0]);barcode(g,20,h*.45,w*.22,ink);});
    }else{
      // Each workflow has its own object: two attribution windows, store lanes,
      // a pending reply envelope or matched price tickets.
      const count=sc.module==='A'?3:2;
      for(let i=0;i<count;i++){
        let a=curve(t,.25+i*.34,.85);
        place(g,x+i*w/count,y+33*Math.sin(t*1.4+i)+(1-a)*130,(i-.5)*.035,a,()=>{
          const bw=w/count-22;sheet(g,0,0,bw,h*.8,i%2?F[2]:paper);
          if(sc.module==='F'){g.strokeStyle=ink;g.lineWidth=8;g.beginPath();g.moveTo(7,25);g.lineTo(bw/2,h*.32);g.lineTo(bw-7,25);g.stroke();}
          if(sc.module==='C'){for(let k=0;k<(i?1:7);k++)box(g,22+k*32,22,22,38,F[0],4);}
          if(sc.module==='A'){box(g,20,22,bw-40,55,F[0]);for(let k=0;k<3;k++)box(g,26,103+k*32,bw-60-(k%2)*24,8,F[0]);}
          if(sc.module==='G'){word(g,sc.values[i],20,76,52,ink,true,bw-30);}
          barcode(g,22,h*.6,bw*.67,ink);
        });
      }
    }
  }
  function cards(g,sc,t,compact=false){
    sc.labels.forEach((s,i)=>{const p=curve(t,.34+i*.69,.59),w=848;
      const x=111+(i%2?1:-1)*540*(1-p)+14*Math.sin(t*1.4+i);
      place(g,x,603+i*197+9*Math.cos(t*1.63+i),.019*Math.sin(t*1.7+i),p,()=>{
        sheet(g,0,0,w,161,i===2?sc.palette[2]:paper);word(g,s,34,78,49,ink,false,410);
        word(g,sc.values[i],450,76,64,ink,true,366);
      });
    });
  }
  const render={
    opening(g,s,t,H,id){const im=H.$(id+'photo');if(im&&im.naturalWidth){g.save();g.globalAlpha=.38;H.drawFrame(g,im,0,-30*t,1080,2030);g.restore();}
      heading(g,s,t);drawBars(g,s,t,118,675,850,445);
      place(g,98,1260,0,curve(t,1.45),()=>{box(g,0,0,865,105,s.palette[0],8);word(g,s.evidence[0]+'   /   '+s.evidence[1],32,52,52,paper);});},
    compare(g,s,t){heading(g,s,t);cards(g,s,t);},
    live(g,s,t,H){heading(g,s,t);const p=curve(t,.08);const frame=H.frame(s,t);
      if(!frame)throw Error('实录场景缺少当前任务素材');
      place(g,82+10*Math.sin(t*1.4),647+80*(1-p)-15*t,.009*Math.sin(t*1.3),p,()=>{
        sheet(g,0,0,915,617,paper);box(g,0,0,915,78,s.palette[2],8);word(g,s.report_title,30,40,36,ink);
        g.drawImage(frame,10,88,895,512);
      });place(g,95,1345,0,curve(t,1.8),()=>word(g,s.report_note,0,0,41,s.palette[1]));},
    align(g,s,t){heading(g,s,t);cards(g,s,t);const x=112+830*(.5-.5*Math.cos(t*1.86));
      g.save();g.globalAlpha=.63;const grad=g.createLinearGradient(x-64,0,x,0);grad.addColorStop(0,'transparent');grad.addColorStop(1,s.palette[1]);box(g,x-60,605,61,553,grad,0);g.restore();
      place(g,117,1290,-.035,curve(t,2.4),()=>{box(g,0,0,729,106,s.palette[2]);word(g,s.evidence[0],34,52,53,ink);});},
    resolution(g,s,t){heading(g,s,t);drawBars(g,s,t,142,567,795,446);
      const p=curve(t,1.1,.56);
      place(g,96,1035+(1-p)*250,.012*Math.sin(t*1.6),p,()=>{sheet(g,0,0,891,288,s.palette[2]);word(g,s.evidence[0],42,64,41,ink);word(g,s.evidence[1],38,182,92,ink,true,780);});
    },
    claim(g,s,t){heading(g,s,t);drawBars(g,s,t,154,565,807,465);}
  };
  function register(name){return {bg:'#172a30',build(s,id,H){
    const photo=name==='opening'?'<img hidden id="'+id+'photo" src="'+H.img(s.image)+'">':'';
    const cta=name==='claim'?K.ctaBlock(id+'c',s,H,{x:84,y:1020,w:534}).html:'';
    return K.layers(id,'<canvas width="1080" height="1920" id="'+id+'board"></canvas>'+photo+cta);
  },anim(s,id,t,H){
    const bg={base:[s.palette[0],s.palette[0],'#0c151c'],seed:17,grid:true,dust:22};
    const beats=[.65,1.8,3.05,4.32,5.55,6.8,8.05,9.3].filter(v=>v<H.dur-.08);
    K.frame(id,t,H,bg,{beats,beat:.045,push:.027});
    const g=H.$(id+'board').getContext('2d');g.clearRect(0,0,1080,1920);render[name](g,s,t,H,id);
    if(name==='claim')K.ctaBlock(id+'c',s,H,{x:84,y:1020,w:534}).anim(t,{show:.5,follow:1.65,type:2.65,send:3.85});
  },sfx:()=>[[.65,'tick'],[1.8,'pop'],[3.05,'ding']]};}
  window.VISUALS=Object.fromEntries(Object.keys(render).map(k=>[k,register(k)]));
  window.VISUALS.outro=K.outro({base:['#1b3031','#112223','#0d181b'],grid:false});
})();

