(() => {
  const {box,label,circle,path,at,live,measured,progress,scene}=window.STORY;
  const bg='#482e54', light='#ffece8', pink='#ff9d9e', lime='#d7e993', deep='#372440';
  function bubble(g,x,y,w,msg,side){
    const c=side?lime:light;
    box(g,x,y,w,125,c,45);
    const tail=side?x+w-55:x+43;
    path(g,[[tail,y+102],[tail+(side?36:-36),y+154],[tail+(side?-28:28),y+118]],c,0,true);
    label(g,msg,x+36,y+60,49,deep,w-64);
  }
  function plane(g,x,y,t){
    at(g,x,y,-.14+.09*Math.sin(t*3),()=>{path(g,[[0,36],[185,-28],[133,84],[99,49],[70,80],[69,50]],pink,0,true);path(g,[[70,50],[160,-9],[100,49]],deep,4);});
  }
  function draw(g,s,t,H,stage){
    const pulse=(Math.sin(t*2.4)+1)/2;
    label(g,'售后值班室    /    工单 C1',61,125,36,pink);
    if(stage==='hook'){
      bubble(g,62,241,635,'我的快递到哪了？',false);
      bubble(g,503,433,510,'工单已处理',true);
      plane(g,116+90*pulse,590,t); label(g,'回复发出去了吗？',286,705,81,light,723);
      live(g,s,t,H,62,876,956,pink,deep,'打开回复记录');measured(g,s,t,68,1468,light);
    }else if(stage==='live'){
      label(g,'查看工单记录',63,324,100,light);
      live(g,s,t,H,45,527,990,pink,deep,'逐单核对');
      bubble(g,385,1220,597,'C1  ·  未回复',true);
    }else if(stage==='compare'){
      bubble(g,74,265,715,'物流查询',false);
      bubble(g,452,517,539,'店内已处理',true);
      box(g,90,902,896,284,'#62446b',45);
      label(g,'草稿箱',124,954,38,pink); plane(g,226+270*pulse,1079,t);
    }else if(stage==='align'){
      label(g,'核对发送凭据',66,317,98,light);
      const y=563;circle(g,205,y,58,lime);circle(g,863,y,58,'#916692');
      path(g,[[267,y],[658,y]],pink,7);
      plane(g,300+240*pulse,y-30,t);
      label(g,'本地处理',92,715,52,lime);label(g,'送达记录',728,715,52,pink);
      bubble(g,64,950,782,'C1   找不到回复凭据',false);
    }else{
      label(g,stage==='claim'?'领取售后助手':'下一单先跟谁？',62,296,90,light);
      bubble(g,71,523,662,'物流查询   C1',false);
      const radius=55+17*pulse;circle(g,163,837,radius,pink);
      path(g,[[163,798],[163,838],[189,853]],deep,7);
      label(g,'超时  ·  仍待回复',261,839,65,light,735);
    }
  }
  for(const st of ['hook','compare','live','align','resolution','claim'])scene('service-reply',st,{bg,beats:[.42,1.52,2.92,4.52]},draw);
})();
