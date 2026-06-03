/// <reference path="jquery/jquery-1.3.2-vsdoc2.js" />
function InitReportDHTML(message) {
    //委托-样品详细链接
    var consignExamResultHrefLink = $("A[title$='hrefToSampleDetail']");
    consignExamResultHrefLink.unbind("click");
    consignExamResultHrefLink.bind("click", function() {
        var ths = $(this);
        var thsTitle = ths.attr("href");
        if (thsTitle.length > 0) {
            var sampleHref = $("TABLE[title$='_" + thsTitle + "_generalSampleInfo']");
            if (sampleHref.length == 1)
                sampleHref.toggleClass("Hide");
            else {
                if (message != null) {
                    message.focus();
                    message.fadeOut("fast");
                    message.fadeIn("fast");
                }
            }
        }
        oeSampleDetailTableOpera();
        return (false);
    });
    //委托展开/关闭所有样品详细信息
    var allSampleInfos = $("TABLE[title$='_generalSampleInfo']");
    var consignAllExamResultHrefLink = $("A[title='hrefToAllSampleDetail']");
    consignAllExamResultHrefLink.unbind("click");
    consignAllExamResultHrefLink.bind("click", function() {
        if (allSampleInfos.length == 0) {
            if (message != null) {
                message.focus();
                message.fadeOut("fast");
                message.fadeIn("fast");
            }
        }
        else {
            //如果有已经显示的则先隐藏掉
            var visibledSampleInfos = allSampleInfos.filter("TABLE").not("TABLE[class*='Hide']");
            if (visibledSampleInfos.length != allSampleInfos.length)
                visibledSampleInfos.addClass("Hide");
            allSampleInfos.toggleClass("Hide");
            oeSampleDetailTableOpera();
        }
        return (false);
    });
}

//样品详细信息间隔颜色处理
function oeSampleDetailTableOpera() {
    var sampleTables = $("TABLE[title$='_generalSampleInfo']").not("TABLE[class*='Hide']");
    if (sampleTables.length > 0) {
        sampleTables.find("TD").removeClass("BackgroundColorA1D3EE BackgroundColorF3F8FD");
        sampleTables.filter("TABLE:odd").find("TD").toggleClass("BackgroundColorA1D3EE");
        sampleTables.filter("TABLE:even").find("TD").addClass("BackgroundColorF3F8FD");
    }
}