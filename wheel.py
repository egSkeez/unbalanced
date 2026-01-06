# wheel.py
import streamlit as st
import streamlit.components.v1 as components
import json

def render_bench_wheel(names):
    if not names:
        st.warning("No players available for the wheel.")
        return

    # Pass names to JS
    names_json = json.dumps(names)
    
    # HTML/JS for the wheel
    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@700&display=swap');
        
        body {{
            background-color: transparent;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            height: 100vh;
            margin: 0;
            font-family: 'Orbitron', sans-serif;
            overflow: hidden;
        }}
        
        #wheel-container {{
            position: relative;
            width: 400px;
            height: 400px;
        }}
        
        canvas {{
            display: block;
            width: 100%;
            height: 100%;
            transform: rotate(-90deg);
        }}
        
        #arrow {{
            position: absolute;
            top: 50%;
            right: -20px;
            transform: translateY(-50%);
            width: 0; 
            height: 0; 
            border-top: 20px solid transparent;
            border-bottom: 20px solid transparent;
            border-right: 40px solid #FFD700;
            z-index: 10;
        }}
        
        #spin-btn {{
            margin-top: 30px;
            padding: 15px 40px;
            font-size: 24px;
            font-family: 'Orbitron', sans-serif;
            background: linear-gradient(45deg, #ff00cc, #3333ff);
            border: none;
            color: white;
            border-radius: 50px;
            cursor: pointer;
            box-shadow: 0 0 20px rgba(255, 0, 204, 0.5);
            transition: transform 0.1s;
        }}
        
        #spin-btn:active {{
            transform: scale(0.95);
        }}
        
        #result {{
            margin-top: 20px;
            font-size: 32px;
            color: #00E500;
            text-shadow: 0 0 10px #00E500;
            min-height: 40px;
        }}
    </style>
    </head>
    <body>
    
    <div id="wheel-container">
        <div id="arrow"></div>
        <canvas id="canvas" width="800" height="800"></canvas>
    </div>
    
    <button id="spin-btn" onclick="spin()">SPIN</button>
    <div id="result"></div>
    
    <script>
        const names = {names_json};
        const colors = ['#FF0000', '#00FF00', '#0000FF', '#FFFF00', '#FF00FF', '#00FFFF', '#FFA500', '#800080', '#008080', '#FFC0CB'];
        const canvas = document.getElementById('canvas');
        const ctx = canvas.getContext('2d');
        const size = 800;
        const center = size / 2;
        const radius = size / 2 - 20;
        let startAngle = 0;
        const arc = 2 * Math.PI / names.length;
        let spinAngleStart = 0;
        let spinTime = 0;
        let spinTimeTotal = 0;
        let currentRotation = 0;

        function drawWheel() {{
            ctx.clearRect(0, 0, size, size);
            
            ctx.save();
            ctx.translate(center, center);
            
            // Outer Glow
            ctx.shadowBlur = 20;
            ctx.shadowColor = "white";
            
            for(let i = 0; i < names.length; i++) {{
                const angle = startAngle + i * arc;
                ctx.fillStyle = colors[i % colors.length];
                
                ctx.beginPath();
                ctx.arc(0, 0, radius, angle, angle + arc, false);
                ctx.arc(0, 0, 0, angle + arc, angle, true);
                ctx.fill();
                
                ctx.save();
                ctx.shadowBlur = 0;
                ctx.fillStyle = "black";
                ctx.font = "bold 40px Arial";
                ctx.translate(
                    Math.cos(angle + arc / 2) * (radius - 120),
                    Math.sin(angle + arc / 2) * (radius - 120)
                );
                ctx.rotate(angle + arc / 2 + Math.PI / 16); // Slight adjust text
                ctx.fillText(names[i], -ctx.measureText(names[i]).width / 2, 0);
                ctx.restore();
            }}
            ctx.restore();
        }}
        
        function rotateWheel() {{
            spinTime += 30;
            if(spinTime >= spinTimeTotal) {{
                stopRotateWheel();
                return;
            }}
            
            const spinAngle = spinAngleStart - easeOut(spinTime, 0, spinAngleStart, spinTimeTotal);
            startAngle += (spinAngle * Math.PI / 180);
            drawWheel();
            requestAnimationFrame(rotateWheel);
        }}
        
        function stopRotateWheel() {{
            const degrees = startAngle * 180 / Math.PI + 90;
            const arcd = 360 / names.length;
            const index = Math.floor((360 - degrees % 360) / arcd);
            
            ctx.save();
            ctx.font = 'bold 80px Arial';
            const text = names[index];
            document.getElementById('result').innerText = "Winner: " + text;
            ctx.restore();
        }}
        
        function easeOut(t, b, c, d) {{
            const ts = (t /= d) * t;
            const tc = ts * t;
            return b + c * (tc + -3 * ts + 3 * t);
        }}
        
        function spin() {{
            spinAngleStart = Math.random() * 10 + 10;
            spinTime = 0;
            spinTimeTotal = Math.random() * 3000 + 4000;
            document.getElementById('result').innerText = "";
            rotateWheel();
        }}
        
        drawWheel();
    </script>
    </body>
    </html>
    """
    
    components.html(html_code, height=600)
