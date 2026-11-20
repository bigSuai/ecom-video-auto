(() => {
  const {box,label,circle,path,at,live,measured,scene}=window.STORY;
  const sprite=new URL('cup-turntable.webp',document.currentScript.src).href;
  scene('ceramic-price','hook',{bg:'#19382f',beats:[.55,1.7,2.55],media:(_,id)=>'<img hidden id="'+id+'cup" src="'+sprite+'">'},(g,s,t,H,stage,id)=>{
    const cream='#fff0ce', orange='#ff7943';
    label(g,'白瓷档案   /   000087',65,102,33,cream);
    circle(g,530,434,284,orange);
    const im=H.$(id+'cup');
    if(im?.naturalWidth){
      const cell=im.naturalWidth/6, n=Math.round(14+14*Math.sin(t*.98));
      g.drawImage(im,(n%6)*cell,Math.floor(n/6)*cell,cell,cell,199,96,660,660);
    }
    s.prices.forEach((v,i)=>{
      const x=i?717:56, y=(i?495:325)+25*Math.sin(t*1.9+i);
      path(g,[[x+123,y],[531,445]],cream,3);
      at(g,x,y,i?.12:-.12,()=>{box(g,0,-45,290,95,i?'#fed172':cream,6);label(g,v,14,3,61,'#204236',264);});
    });
    label(g,'一只杯子，两张价签',63,761,82,cream);
    live(g,s,t,H,70,900,940,'#f6ce77','#17372c','打开查价报告');
    measured(g,s,t,75,1465,cream);
  });
})();
