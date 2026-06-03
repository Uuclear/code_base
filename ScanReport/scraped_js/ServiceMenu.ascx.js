var targetMenuItem = null;
var slidedownMenuObj = null;
var ifonServices = false;
var tmoSTO = null;

function ViewServiceInterface() {
    targetMenuItem.parentNode.appendChild(slidedownMenuObj);
    slidedownMenuObj.style.marginTop = targetMenuItem.offsetHeight + targetMenuItem.style.top;
    slidedownMenuObj.style.marginLeft = -1 * targetMenuItem.offsetWidth + targetMenuItem.style.left;
    slidedownMenuObj.style.display = "inline";
    ifonServices = true;
    return false;
}

function HideServiceInterface() {
    tmoSTO = window.setTimeout("if (!ifonServices){slidedownMenuObj.style.display = \"none\";window.clearTimeout(tmoSTO);}", 1000);
    return false;
}


function Load() {
    initSlideDownMenu();

    var aArray = document.getElementsByTagName('a');
    for (var i = 0; i < aArray.length; i++) {
        if (aArray[i].href.indexOf('serviceMenuLink') >= 0)
            targetMenuItem = aArray[i];
    }
    if (targetMenuItem) {
        slidedownMenuObj = document.getElementById("slidedownMenu");
        targetMenuItem.onclick = null;
        targetMenuItem.onclick = function() { return false };
        targetMenuItem.onmouseover = null;
        targetMenuItem.onmouseover = ViewServiceInterface;
        targetMenuItem.onmouseout = null;
        targetMenuItem.onmouseout = function() {
            ifonServices = false;
            HideServiceInterface();
        };
        slidedownMenuObj.onmouseover = function() {
            ifonServices = true;
        };
        slidedownMenuObj.onmouseout = function() {
            ifonServices = false;
            HideServiceInterface();
        };
        //slidedownMenuObj.onclick = function() { blur(); }
    }
}

//window.onload = Load;//停止使用