var mousePressed = false;
var lastX, lastY;
var ctx;
var d, b64_text, prediction, confidence;

function InitThis() {
    ctx = document.getElementById('myCanvas').getContext("2d");

    $('#myCanvas').mousedown(function (e) {
        mousePressed = true;
        Draw(e.pageX - $(this).offset().left, e.pageY - $(this).offset().top, false);
    });

    $('#myCanvas').mousemove(function (e) {
        if (mousePressed) {
            Draw(e.pageX - $(this).offset().left, e.pageY - $(this).offset().top, true);
        }
    });

    $('#myCanvas').mouseup(function (e) {
        mousePressed = false;
    });
	    $('#myCanvas').mouseleave(function (e) {
        mousePressed = false;
    });
}

function Draw(x, y, isDown) {
    if (isDown) {
        ctx.beginPath();
        ctx.strokeStyle = $('#selColor').val();
        ctx.lineWidth = 30;
        ctx.lineJoin = "round";
        ctx.moveTo(lastX, lastY);
        ctx.lineTo(x, y);
        ctx.closePath();
        ctx.stroke();
    }
    lastX = x; lastY = y;
}
	
function clearArea() {
    // Use the identity matrix while clearing the canvas
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
}

function saveimage() {
	// body...
	var c=document.getElementById("myCanvas");
	d=c.toDataURL("image/png");
	//var w=window.open('about:blank','image from canvas');
	//w.document.write("<img src='"+d+"' alt='from canvas'/>");
    d = d.toString();
    b64_text = d.split('base64,')[1];
}

function getOutput(){
	//send the image 
	//get text as o/p
	//set the image url as  that number.jpg
    data = {
        "b": b64_text
    }
	
    $.ajax({
    type: 'POST',
    url: '/send-info',
    data: JSON.stringify(data),
    dataType: 'json',
    contentType: 'application/json; charset=utf-8'
    }).done(function(msg) {
    console.log(msg);
    prediction = msg["prediction"]["results"]["prediction"];
    confidence = msg["prediction"]["results"]["confidence"][prediction];
    var s = "";    
    s = "/static/images/"+prediction+".png";
            
    document.getElementById("output").setAttribute("src",s);
    document.getElementById("c").innerHTML = "Confidence level "+ confidence + "%";
    console.log(prediction);
    console.log(confidence);
    });

   
}