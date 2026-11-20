(() => {
  const {box,label,path,circle,at,live,measured,progress,scene}=window.STORY;
  const bg='#542b30', cream='#fff0cc', coral='#ffa778', dark='#452628';
  const sprite=new URL('cup-turntable.webp',document.currentScript.src).href;
  const media=(_,id)=>'<img hidden id="'+id+'cup" src="'+sprite+'">';
  function print(g,img,x,y,w,r,i,t){
    at(g,x,y,r,()=>{
      box(g,7,11,w,w*1.02,'#341d22',3);box(g,0,0,w,w*1.02,cream,3);
      box(g,13,12,w-26,w*.72,['#da965b','#bfc999','#c7add0','#9abec0'][i]);
      if(img?.naturalWidth){
        const n=(i*6+Math.floor(t*4))%30,cell=img.naturalWidth/6;
        g.drawImage(img,(n%6)*cell,Math.floor(n/6)*cell,cell,cell,w*.14,0,w*.72,w*.72);
      }
      label(g,['主图','详情','图文','短视频'][i],21,w*.88,w*.125,dark,w-41);
      if(i===3){circle(g,w*.74,w*.61,w*.105,dark);path(g,[[w*.71,w*.55],[w*.71,w*.67],[w*.8,w*.61]],cream,0,true);}
    });
  }
  function prints(g,img,t,y,w,split){
    const p=.40+.60*progress(t,0,1.5);
    for(let i=0;i<4;i++)print(g,img,416+(i-1.5)*split*p,y+Math.abs(1.5-i)*30+13*Math.sin(t*1.8+i),w,(i-1.5)*.125,i,t);
  }
  function draw(g,s,t,H,stage,id){
    const img=H.$(id+'cup');
    label(g,'陶瓷杯   /   素材编辑室',57,116,37,coral);
    if(stage==='hook'){
      label(g,'一只杯子的',59,253,98,cream);label(g,'四份初稿',61,378,119,coral);
      prints(g,img,t,472,228,215);
      live(g,s,t,H,55,883,970,cream,dark,'现场选稿与导出');measured(g,s,t,63,1471,cream);
    }else if(stage==='live'){
      label(g,'选中这张主图',60,288,93,cream);
      live(g,s,t,H,48,475,984,cream,dark,'查看文件导出');
      print(g,img,671,1125,208,.09,0,t);label(g,'导出主图',72,1244,70,coral,557);
    }else if(stage==='compare'){
      label(g,'同一份商品资料',63,290,91,cream);
      print(g,img,376,458,307,-.04,0,t);
      path(g,[[539,798],[539,889],[156,889],[156,961]],coral,5);
      path(g,[[539,889],[925,889],[925,961]],coral,5);
      prints(g,img,t,967,225,220);
    }else if(stage==='align'){
      label(g,'生成后，谁被选中？',59,302,84,cream);
      prints(g,img,t,522,225,225);
      const y=1040-98*progress(t,.65,1.6);
      print(g,img,132,y,272,-.1,0,t);label(g,'主图   已选',528,1101,72,coral,460);
    }else{
      label(g,stage==='claim'?'领取素材助手':'把选中的版本导出',62,304,83,cream);
      const slide=progress(t,.3,1.8);box(g,382,682,575,258,'#bc6b50',20);
      print(g,img,152+315*slide,510+115*slide,293,-.13*(1-slide),0,t);
      box(g,382,837,575,124,coral,15);label(g,'主图  /  EXPORT',410,896,49,dark);
    }
  }
  for(const st of ['hook','compare','live','align','resolution','claim'])scene('media-drafts',st,{bg,media,beats:[.44,1.42,2.82,4.23]},draw);
})();
