<%@ Language=VBScript %>
<% 
Response.Expires = 0 
Response.Expiresabsolute = Now() - 1 
Response.AddHeader "pragma","no-cache" 
Response.AddHeader "cache-control","private" 
Response.CacheControl = "no-cache" 
%> 

<%title="Container Image"%>
<!--#include file="security.asp" -->

<%
dim bContainerAdmin

Response.Write("<SCRIPT LANGUAGE=Javascript>" & vbCrLf)
if UserHasPageAccess("ContainerAdmin.asp") then
	Response.Write("bContainerAdmin=true;" & vbCrLf)
	bContainerAdmin=true
else
	Response.Write("bContainerAdmin=false;" & vbCrLf)
	bContainerAdmin=false
end if
Response.Write("</SCRIPT>" & vbCrLf)

Dim cn,cmd,objRS,sql, strConn, set_name,graphic_data,file_name,description, _
graphic_height,graphic_width,set_id,graphic_id,action,set_graphics_id,errmsg

dim selImages
selImages=""
errmsg=""
action=""
'defaults for initial page:

strConn = GetConnectionString
set rs = Server.CreateObject("ADODB.Recordset")



'create default due time by rounding current time up to nearest hour
function DueTime()
	t=now
	t=DateAdd("h",1,t)
	t=DateAdd("s",0-DatePart("s",t),t)
	t=DateAdd("n",0-DatePart("n",t),t)
	DueTime=t
end function

function BatchSel
	dim s
	s="<select id=selBatch name=selBatch><option value=0 selected>...All Schedules...</option>"
	sql = "SELECT min(schedule_id), batch_name from Schedule group by batch_name order by 2" 
	rs.Open sql, strConn, , , adCmdText
	do until rs.EOF
		s=s & "<option value=" & rs(0) & ">" & server.HTMLEncode(rs(1)&"") & "</option>"
		rs.MoveNext
	loop
	rs.Close 
	s=s & "</select>"
	BatchSel=s
end function

function ProcessSel
	dim s
	s="<select id=selProcess name=selProcess>"
	sql = "SELECT process_type_id, process_name from ProcessType order by 1" 
	rs.Open sql, strConn, , , adCmdText
	do until rs.EOF
		s=s & "<option value=" & rs(0) & ">" & rs(1) & "</option>"
		rs.MoveNext
	loop
	rs.Close 
	s=s & "</select>"
	ProcessSel=s
end function

function GroupSel
	dim s
	s="<select id=selGroup name=selGroup><option value=''>...None...</option>"
	sql = "SELECT group_id, group_name from LocationProcessGroup  order by 2" 
	rs.Open sql, strConn, , , adCmdText
	do until rs.EOF
		s=s & "<option value=" & rs(0) & ">" & rs(1) & "</option>"
		rs.MoveNext
	loop
	rs.Close 
	s=s & "</select>"
	GroupSel=s
end function


%>
<html>
<head>
<script language=javascript>
<!--
var fileData=''

//***************************************** Remote Scripting Section BEGIN
<!--#include file="_ScriptLibrary/rs.htm" -->
RSEnableRemoteScripting();

rmt = new Object;
rmt.location = "ScheduleRS.asp";
rmt.execute = new Object;
rmt.execute.AddSchedule = Function('batch_name','rows', 'offset_first_due', 'return MSRS.invokeMethod(rmt.location, "AddSchedule", this.AddSchedule.arguments);');
rmt.execute.AddScheduleItem = Function('batch_name', 'case_ref', 'set_name', 'set_ref', 'dest_name', 'group_id', 'process_type_id', 'due_timestamp', 'priority', 'fUpdate', 'return MSRS.invokeMethod(rmt.location, "AddScheduleItem", this.AddScheduleItem.arguments);');
rmt.execute.DeleteSchedule = Function('batch_name', 'return MSRS.invokeMethod(rmt.location, "DeleteSchedule", this.DeleteSchedule.arguments);');
rmt.execute.GetContainerList = Function( 'return MSRS.invokeMethod(rmt.location, "GetContainerList", this.GetContainerList.arguments);');
rmt.execute.GetLocationList = Function( 'return MSRS.invokeMethod(rmt.location, "GetLocationList", this.GetLocationList.arguments);');
rmt.execute.GetErrorList = Function('batch_name', 'return MSRS.invokeMethod(rmt.location, "GetErrorList", this.GetErrorList.arguments);');

var g_errorRow;
function ContainerListCallback(result){
	if(result==null){

	}else{
		if(form1.txtSet_name.value!=result[0]){
			form1.txtSet_name.value=result[0]
		}
		checkForm()
	}
}

function loadContainerList(){
	if(form1.btnLoadContainerList.value!='Get List')return setContainerName();
	var retObj=rmt.execute.GetContainerList()
	txtContainerList.value=retObj.return_value;
	containerPopup= new _PopupText(txtContainerList,form1.txtSet_name,ContainerListCallback);
	containerPopup.minSearch=0;
	containerPopup.width=Math.max(500,containerPopup.width)
	//form1.btnLoadContainerList.disabled=true
	form1.btnLoadContainerList.value='Accept'
	AlertUser('Container List Loaded')
}

function setContainerName(){
	if(g_errorRow)g_errorRow.cells(2).innerText=form1.txtSet_name.value
}

function LocationListCallback(result){
	if(result==null){

	}else{
		if(form1.txtDest.value!=result[0]){
			form1.txtDest.value=result[0]
		}
		checkForm()
	}
}

function loadLocationList(){
	if(form1.btnLoadLocationList.value!='Get List')return setLocationName();
	var retObj=rmt.execute.GetLocationList()
	txtLocationList.value=retObj.return_value;
	locationPopup= new _PopupText(txtLocationList,form1.txtDest,LocationListCallback);
	locationPopup.minSearch=0;
	locationPopup.width=Math.max(500,locationPopup.width)
	//form1.btnLoadLocationList.disabled=true
	form1.btnLoadLocationList.value='Accept'
	AlertUser('Location List Loaded')
}

function setLocationName(){
	if(g_errorRow)g_errorRow.cells(2).innerText=form1.txtDest.value
}


function form1_onsubmit(){
	if(!checkForm())return false;
	//try to use fsb for all, must use for scaled or rotated since file1 is unscaled/unrotated and there is no way to upload an arbitrary file, only one chosen by the user
	var fs=(scaledFile!='')?scaledFile:form1.File1.value 
	var result=StoreImageFsb(fs,form1).split('\t')
	if(result=='' && scaledFile=='')return true; //fsb not supported so submit form
	if(result.length>1){
		//success
		//update selExisting based on mode
		if(form1.mode.value=='add'){
			with(form1.selExisting.options){
				var m=length;
				var	opt=document.createElement("OPTION");
				opt.text=form1.description.value;
				opt.value=result[0]
				add(opt);
				form1.selExisting.selectedIndex=m
			}
			selExisting_onchange()
		} else if(form1.mode.value=='update'){
			//currently selected option gets new value and text
			var opt=form1.selExisting.options(form1.selExisting.selectedIndex)
			opt.value=result[0]
			opt.text=form1.description.value;
			selExisting_onchange()
		} else if(form1.mode.value=='delete'){
			with(form1.selExisting){
				var i=selectedIndex
				//this doesn't help, IE always picks first option after remove
				//var n=options.length-2
				//if(n>0)selectedIndex=(n<i)?i-1:i; //select the one before the one we deleted
				options.remove(i)
			}
		}
		AlertUser(result[1])
	} else AlertUser(result[0]) //failed
	return false //cancel submit
}

function btnAdd_onclick(fUpdate){
	if(!checkForm())return 
	if(fUpdate=='Y'){
		if(!findBatch())return
		if(!btnDelete_OnClick(fUpdate))return
	}
	//let screen repaint before import, because exe does do "Loading"
	ClearTable(ReportTable)
	form1.btnExport.disabled=true
	setAllButtonStyle();
	AlertUser("Processing, Please Wait...")
	window.setTimeout("importBatch()",30)
}

function importBatch(){	
	var batch_name=GetFileName() 
	var fs=form1.File1.value 
	if(batch_name=='')batch_name=form1.description.value
	//if(fileData=='')fileData=getManualData()
	//var ts_first_Due=('1004,1007'.indexOf(window.parent.GetCookie('clientid'))==-1)?'':4;
	var return_value
	if(fileData==''){
		return_value=AddManual(fUpdate)
	}else{
		var offset_first_due=(typeof(form1.txtFirstDue)=='object')?form1.txtFirstDue.value:'';
		//var retObj=rmt.execute.AddSchedule(batch_name,fileData, offset_first_due)
		//return_value=retObj.return_value
		return_value=StoreImageFsb(fs,batch_name,offset_first_due)
	}
	if( return_value=='ok'){
		if(!findBatch()){
			var oOption = document.createElement("OPTION");
			form1.selBatch.options.add(oOption)
			oOption.innerText = batch_name;
			oOption.Value = -1;
			oOption.selected=true;
		}
		checkForm() //update button status
		AlertUser('Schedule Imported')
	}else if ( return_value=='') AlertUser('Import Failed due to Server Error')
	else AlertUser('Import Failed: '+return_value)
}

function AddManual(fUpdate){
	var batch_name=form1.description.value
	var case_ref=form1.txtCase.value
	var set_name=form1.txtSet_name.value
	var dest=form1.txtDest.value
	var due=form1.txtDue.value
	var retObj=rmt.execute.AddScheduleItem(batch_name, case_ref, set_name, '', dest, '', '', due, '', fUpdate)
	return retObj.return_value
}

function checkImage(){
var r = false;
	if (img.fileSize>(1024*200)){
		AlertUser("The image file size (" + Math.round((img.fileSize/1024)) + "kb) is too large. It should not exceed 200kb.");
	}else{
		r = true;
	}

	form1.btnAdd.disabled=!r || form1.File1.value=='';
	form1.btnUpdate.disabled=!r;
	setAllButtonStyle();
	
	return r;
}



function loadFile(){
	ClearAlert()
	fileData=''
	if(checkFileName()){
		//var fs=form1.File1.value
		//fileData=ReadFileFsb(fs)
		fileData='Y'
		checkForm() 
	}
}

function checkFileName(){
	var fs=form1.File1.value
	if(fs=='')return false
	var a=fs.split('.')
	var ext=a[a.length-1].toLowerCase()
	if(ext=='xls'){
		AlertUser("Excel files won't import, save as CSV or Text format")
		return false
	}
	if(ext!='csv' && ext!='txt'){
		AlertUser("Unexpected file type, might not import, requires CSV or Text format")
		//just a warning
	}
	return true
}

function checkForm(){

	//only check manual fields if file name is blank
	if(form1.File1.value!=''){
		if(fileData==''){
			form1.btnUpdate.disabled=true
			form1.btnAdd.disabled=true
			setAllButtonStyle();
			return false;
		}else{
			var b=findBatch()
			form1.btnUpdate.disabled=!b
			form1.btnAdd.disabled=b
			setAllButtonStyle();
			return true
		}
	}
	
}

function getManualData(){
	var s='case_ref, qty, set_name, dest_name, due_timestamp\r"'
	s+=form1.txtCase.value+'",1,"'
	s+=form1.txtSet_name.value+'","'
	s+=form1.txtDest.value+'","'
	s+=form1.txtDue.value+'"'
	return s
}

function btnDelete_OnClick(fUpdate){
	var batch=''
	var verb=(fUpdate=='Y')?'replace':'delete';
	if(form1.selBatch.selectedIndex==0){
		if (!confirm("Are you sure you want to "+verb+" all current Schedules?"))return false
	}else{
		batch=form1.selBatch.options(form1.selBatch.selectedIndex).text
		if (!confirm("Are you sure you want to "+verb+" the Schedules from the selected batch \r'"+batch+"'?"))return false
	}
	
	//if(fUpdate=='Y' && form1.File1.value=='')return true; //let the import call do the delete
	if(fUpdate=='Y')return true; //let the import call do the delete for both manual and file
		
	ClearTable(ReportTable)
	form1.btnExport.disabled=true
	setAllButtonStyle();

	var retObj=rmt.execute.DeleteSchedule(batch)
	if( retObj.return_value=='ok'){
		 AlertUser('Schedule Deleted')
		 if(batch!='')form1.selBatch.options.remove(form1.selBatch.selectedIndex)
		 else{ //delete all but the default
			var i, opts=form1.selBatch.options, n=opts.length
			for(i=n-1; i>0; i--)opts.remove(i)
		 }
		 if(fUpdate!='Y')checkForm() //update button status
		 return true;
	}else if ( retObj.return_value=='') AlertUser('Delete Failed due to Server Error')
	else AlertUser('Delete Failed: '+retObj.return_value)
	return false
}

function getErrors(){
	var batch=''
	if(form1.selBatch.selectedIndex>0)
		batch=form1.selBatch.options(form1.selBatch.selectedIndex).text
	
	ClearTable(ReportTable) ;
	var retObj=rmt.execute.GetErrorList(batch)
	if( retObj.return_value=='ok'){
		 AlertUser('No Errors Found')
	}else{
		lst=retObj.return_value.split('\r')
		n=lst.length-1;
		for(var i=0;i<n;i++){
			AddTableRowEx(lst[i])
		}
		form1.btnExport.disabled=false
		setAllButtonStyle();
	}
}

function tbError_ondblclick(){
	var src=event.srcElement
	var s=''
	if(document.selection.type=='Text'){
		s=document.selection.createRange().text.trim()
	}
	if(s!=''){
		if(src.tagName=='DIV')td=src.parentElement
		else td=src
		if(td.tagName!='TD')return
		tr=td.parentElement
		if(td.cellIndex==1)return; //clicking on a ref num does nothing
		g_errorRow=tr; //remeber row for correction
		if(tr.cells(1).innerText=='(Location)'){
			form1.txtDest.value=s
			if(typeof(locationPopup)=='object')locationPopup.displayList()
		}else{
			form1.txtSet_name.value=s
			if(typeof(containerPopup)=='object')containerPopup.displayList()
		}
	}
}
//when user selects a range of text in the errors table, try to find matches
function tbError_onmouseup(){
	if(event.button==1)tbError_ondblclick() //only left button
}
function hint(){
	var src=event.srcElement;
	var p=createPopup()
	p.document.write("<body style='margin:0;background-color:silver;overflow:hidden;'><center>Double-Click a word to search for it, or drag the mouse to highlight text and search for it, after using 'Get List'</center></body>")
	p.show(-200,30,400,45,src)
}

function AddTableRowEx(strRowData){
	// breakdown return string
	var rowData = strRowData.split("\t");
	var n=rowData.length; 
											
	//Add Item to List
	var addRow, addCell;
	
	//add row
	addRow = ReportTable.insertRow();
	addRow.className='aRow' //for Export
	
	//add TDs(Cells) and Populate	
	for (var i=0; i<n; i++){
		addCell=addRow.insertCell();
		addCell.innerHTML = "&nbsp;"
		if(rowData[i] && rowData[i]!='')addCell.innerText = rowData[i]
	}
	//extra cell for censitrac name
	addCell=addRow.insertCell();
	addCell.innerHTML = "&nbsp;"
}

function ClearTable(tb){
	var i;
	var n=tb.rows.length-1;
	for(i=n;i>-1;i--)tb.deleteRow(i);
	g_errorRow=undefined
}

function findBatch(){
	//attempt to select the file name in the existing batch select
	var i, opts=form1.selBatch.options, n=opts.length, fs=GetFileName();
	if(fs=='')fs=form1.description.value 
	for(i=1; i<n; i++)if(opts(i).text==fs){opts(i).selected=true; return true}
	return false;
}

function GetFileName(){
	//return name with path removed
	var fs=form1.File1.value
	if(fs!=''){
		p=fs.lastIndexOf('\\')
		if(p==-1)p=fs.lastIndexOf('/')
		if(p>-1)return fs.substr(p+1)
	}
	return fs
}

function window_onload(){
	if(typeof(form1.txtFirstDue)=='object' && ('1004,1007'.indexOf(window.parent.GetCookie('clientid'))==-1))form1.txtFirstDue.value=''

	//hack for bug in Export in Censitrac.exe, certain objects expected in report frame,
	//ie. fr.Document.All.Item("columnDatatypes").value
	//as of exe version 1.1.0.222
	document.Document=new Object();
	document.Document.All=new Object;
	document.Document.All.Item=_exportAllItem;
}

function _exportAllItem(objName){
	//hack for bug in Export in Censitrac.exe, certain objects expected in report frame,
	//ie. fr.Document.All.Item("columnDatatypes").value
	//but when report frame doesn't exist, fr is document so syntax does not work without this hack
	//alert(objName)
	return document.all(objName);
}

function NoFile(){
	//input type=file cannot be cleared except by resetting the form
	//var gr=form1.graphic_id.value
	form1.reset()
	form1.text1.value='';
	//form1.graphic_id.value=gr;
	valid_file=false
}

function ReadFileFsb(fs){
	return HeaderFsbCmd('ReadFile',fs)
}
function StoreImageFsb(fs,batch_name,offset_first_due){
	var qs='type=schedule'
	qs+='&offset_first_due='+offset_first_due+'&batch_name='+batch_name
	return HeaderFsbCmd('StoreImage',fs,qs)
}

//-->
</script>
<style>
#mainDiv  {text-align:center;width:100%;}
@media screen {
	#divError {height:12em;overflow:auto;border:1px solid black}
	thead { display: none }
}
@media print {
	#divError {border:1px solid black}
	thead { display: table-header-group; font-weight:bold; }
}
</style>
</head>
<body onload="window_onload();">
<div id="mainDiv">
	<DIV align=center ID=errorMsg> </DIV>
	<form onsubmit="return form1_onsubmit();" name=form1 method=post >
		<input name="mode" type=hidden>
		<TABLE align=center border=0 cellPadding=1 cellSpacing=1 width="95%" ID="Table1">
		<TR>
			<TD align=center colspan=2><STRONG>Existing Schedules:</STRONG>&nbsp;&nbsp;
			<%=BatchSel%>
		<TR>
			<TD align=center colspan=2>
			<INPUT onclick="btnDelete_OnClick('N');" type="button" value="Delete" ID="btnDelete" NAME="btnDelete">
			&nbsp;&nbsp;
			<input type=button id=btnErrors value='Review Errors' onclick=getErrors()>
			&nbsp;&nbsp;
			<input type=button id=btnExport value='Export Errors' disabled=true>
		<TR>
			<TD align=center colspan=2><STRONG>Review Errors: <a onclick=hint() style='cursor:help;text-decoration=underline;color:#007cc1;'>Hint</a></STRONG></td>
		<TR>
			<TD align=center colspan=2><div id=divError> <table id=tbError ondblclick=tbError_ondblclick() onmouseup=tbError_onmouseup()>
				<thead><tr id=rowHead><td>Item Name<td>Item Ref<td>Censitrac Name</TR></thead>
				<tbody id=ReportTable></tbody>
			</table></div>
		<TR>
			<TD align=right><STRONG>Find destination:</STRONG></td>
			<td><input type=text id=txtDest name=txtDest size=60>&nbsp;&nbsp;<input type=button name=btnLoadLocationList onclick=loadLocationList() value='Get List'>
		<TR>
			<TD align=right><STRONG>Find container:</STRONG></td>
			<td><input type=text id=txtSet_name name=txtSet_name size=60>&nbsp;&nbsp;<input type=button name=btnLoadContainerList onclick=loadContainerList() value='Get List'>
		<TR>
			<TD align=center colspan=2> &nbsp;
		<TR>
			<TD align=right><STRONG>Import File:</STRONG></td>
			<td><INPUT size=60 type="file" ID="File1" NAME="File1" onchange="text1.value=this.value;loadFile();" style="display:none">
				<INPUT size=60 id=text1 name=text1 readonly>&nbsp;<INPUT type=button value="Browse..." id=button1 name=button1 onclick="File1.click();">
		<TR>
			<TD align=center colspan=2>
			<STRONG>Test File Adjustment, set first requirement due</STRONG>
			<%if GetSessionVariable("client_id")="1007" then%>
			<input type=text id="txtFirstDue" name="txtFirstDue" maxlength=3 size=3 value="4">
			<STRONG>Hours from now.</STRONG>
			<%else%>
			<input type=text id="Text2" name="txtFirstDue" maxlength=3 size=3 value="1">
			<STRONG>Days from today.</STRONG>
			<%end if%>
			
		<TR>
			<TD align=center colspan=2>
			<INPUT disabled type="button" value="Add"  ID="btnAdd" NAME="btnAdd"  onclick=btnAdd_onclick('N')>&nbsp;
			<INPUT disabled type="button" value="Update" ID="btnUpdate" NAME="btnUpdate"  onclick=btnAdd_onclick('Y')>
			</TD></TR>		
		</table>
	</form>
</div>
<input type=hidden id=txtContainerList>
<input type=hidden id=txtLocationList>
<input type=hidden name="BrowserType" value="IE">
<input type=hidden id=columnDatatypes value="x:str,x:str,x:str">
<div style='display:none' id=ReportTitle>Scheduling--Import Errors</div>

<!--#include file="includes/PopupText.asp" -->

<!--#include file="includes/footer2.html"-->