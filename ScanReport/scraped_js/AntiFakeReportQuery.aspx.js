/// <reference path="jquery/jquery-1.3.2-vsdoc2.js" />
$(document).ready(function() {
    var message;
    //查询条件
    var submitQuery = $("INPUT[id$='bttnQuery']");
    var conditionBar = $("#antiFakeReportQueryContainer > DIV.Content > DIV.ConditionBar");
    var inputs = conditionBar.find("DIV.Content TABLE TR TD INPUT");
    var qReportID = inputs.filter("INPUT[id$='qReportID']");
    var qIdentifyingCodeInput = inputs.filter("INPUT[id$='qIdentifyingCode']");
    message = conditionBar.find("DIV[id$='message']");
    qReportID.attr("maxLength", "20");
    qReportID.unbind("mouseover");
    qReportID.bind("mouseover", function() {
        this.select();
    });
    qIdentifyingCodeInput.attr("maxLength", "12");
    qIdentifyingCodeInput.unbind("mouseover");
    qIdentifyingCodeInput.bind("mouseover", function() {
        this.select();
    });

    submitQuery.unbind("click");
    submitQuery.bind("click", function() {
        if (qReportID.val().length == 0) {
            message.text("请输入报告编号.");
            message.show();
            return (false);
        }
        if (qIdentifyingCodeInput.val().length == 0) {
            message.text("请输入防伪校验码.");
            message.show();
            return (false);
        }
        submitQuery.unbind("click");
        $(this).css("display", "none");
    });
    //查询-检测单位选择
    var ddl = $("#antiFakeReportQueryContainer SELECT[id$='qDetectionUnit_ddl']");
    ddl.unbind("change");
    ddl.bind("change", function() {
        var qDetection = $("INPUT[id$='qDetectionUnit']");
        qDetection.val(ddl.val());
    });
    //info框
    var infoBar = $("DIV[id$='info'] > TABLE");
    var info_LeftPic = infoBar.find("IMG[alt='info_LeftPic']");
    var info_RightPic = infoBar.find("IMG[alt='info_RightPic']");
    infoBar.unbind("mouseover");
    infoBar.unbind("mouseout");
    infoBar.bind("mouseover", function() {
        infoBar.css({ color: "#fff", backgroundColor: "#13286B" });
        info_LeftPic.attr("src", "../images/info_LeftPic2.JPG");
        info_RightPic.attr("src", "../images/info_RightPic2.JPG");
    });
    infoBar.bind("mouseout", function() {
        infoBar.css({ color: "#000", backgroundColor: "#FFFFE1" });
        info_LeftPic.attr("src", "../images/info_LeftPic.JPG");
        info_RightPic.attr("src", "../images/info_RightPic.JPG");
    });
    info_RightPic.unbind("click");
    info_RightPic.bind("click", function() {
        infoBar.hide();
    });
    //resultInfo框
    var queryResultInfoBar = $("DIV[id$='queryResultInfoBar']");
    var dataTableBar = $("DIV[id$='dataTableBar']");
    var rightIMG = queryResultInfoBar.find("IMG[src$='right.png']");
    if (rightIMG.length == 1) {
        rightIMG.unbind("click");
        rightIMG.bind("click", function() {
            queryResultInfoBar.css("display", "none");
            dataTableBar.css("display", "block");
        });
    }
    var hitHereSpan = queryResultInfoBar.find("DIV[id$='queryResultInfoBarContent'] > A");
    hitHereSpan.unbind("click");
    hitHereSpan.bind("click", function() {
        queryResultInfoBar.css("display", "none");
        dataTableBar.css("display", "block");
        return (false);
    });
    //初始化报告的动态脚本
    InitReportDHTML(message);
}); 