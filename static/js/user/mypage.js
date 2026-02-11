console.log("user.mypage.js is called.")

const fm = new FileManager(".center");
fm.build();

const rj = new RequestData()
let ed = null;
rj.fetchFile("/user/file",{path:"etc/data/sample.xlsx"}).then((f)=>{
    ed = new ExcelData(f);
});
