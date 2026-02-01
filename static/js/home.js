console.log("canvas.js");

// const canv = new Canvas(".center");
// const doodle = new Doodle(".center");


// const back = new CanvasBackGround(0,0,2,0,0);
// const rect1 = new CanvasObject(19,19,1,199,100);
// const rect2 = new CanvasObject(19,423,1,159,100);
// const rect3 = new CanvasObject(19,123,4,199,245);
// const rect4 = new CanvasRect(3,223,4,239,545);


// canv.append(back);
// canv.append(rect1);
// canv.append(rect2);
// canv.append(rect3);
// canv.append(rect4);

// canv.loop();
// doodle.draw();


const g = new GridFixLocal(128,128,64,64,".center");
const tabpage = new TabPage();
tabpage.x = 1;
tabpage.y = 1;
tabpage.w = 10;
tabpage.h = 10;
tabpage.build();
tabpage.movable(()=>{});
tabpage.sizable(()=>{});
tabpage.turn_page(0);
const page = DOM.create("div");
page.innerHTML = "aaaa";
tabpage.append("page1",page);
g.append(tabpage.id,tabpage);
g.draw();

const go = new GridObject("body",4,4,1,4,4);
go.build();
go.movable(()=>{});
go.sizable(()=>{});
g.append(go.id,go);
g.draw();
const editor = new Editor(go.contents);


document.addEventListener("DOMContentLoaded",()=>{
    g.draw();
});

