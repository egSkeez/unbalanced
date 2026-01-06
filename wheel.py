# wheel.py
import streamlit as st
import streamlit.components.v1 as components
import json

def render_bench_wheel(names, winner_label="Winner", target_winner=None):
    if not names:
        st.warning("No players available for the wheel.")
        return

    names_json = json.dumps(names)
    label_json = json.dumps(winner_label)
    # If a target is passed, pass it to JS, otherwise null (random spin)
    target_json = json.dumps(target_winner) if target_winner else "null"
    
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
            /* Rotate -90deg so 0 is at Top */
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
        
        #result {{
            margin-top: 20px;
            font-size: 32px;
            color: #00E500;
            text-shadow: 0 0 10px #00E500;
            min-height: 40px;
            text-align: center;
        }}
    </style>
    </head>
    <body>
    
    <div id="wheel-container">
        <div id="arrow"></div>
        <canvas id="canvas" width="800" height="800"></canvas>
    </div>
    
    <div id="result"></div>
    
    <script>
        const names = {names_json};
        const winnerLabel = {label_json}; 
        const targetWinner = {target_json}; // Received from Python
        
        const colors = ['#FF0000', '#00FF00', '#0000FF', '#FFFF00', '#FF00FF', '#00FFFF', '#FFA500', '#800080', '#008080', '#FFC0CB'];
        const canvas = document.getElementById('canvas');
        const ctx = canvas.getContext('2d');
        const size = 800;
        const center = size / 2;
        const radius = size / 2 - 20;
        
        let startAngle = 0; // Current rotation
        const arc = 2 * Math.PI / names.length;
        
        // Animation variables
        let startTime = null;
        let duration = 6000; // 6 Seconds
        let startRotation = 0;
        let targetRotation = 0;
        let isSpinning = false;

        function drawWheel() {{
            ctx.clearRect(0, 0, size, size);
            
            ctx.save();
            ctx.translate(center, center);
            ctx.rotate(startAngle); // Rotate the whole canvas content
            
            // Outer Glow
            ctx.shadowBlur = 20;
            ctx.shadowColor = "white";
            
            for(let i = 0; i < names.length; i++) {{
                const angle = i * arc;
                ctx.fillStyle = colors[i % colors.length];
                
                ctx.beginPath();
                ctx.arc(0, 0, radius, angle, angle + arc, false);
                ctx.arc(0, 0, 0, angle + arc, angle, true);
                ctx.fill();
                
                ctx.save();
                ctx.shadowBlur = 0;
                ctx.fillStyle = "black";
                ctx.font = "bold 40px Arial";
                
                // Text position
                ctx.translate(
                    Math.cos(angle + arc / 2) * (radius - 120),
                    Math.sin(angle + arc / 2) * (radius - 120)
                );
                ctx.rotate(angle + arc / 2 + Math.PI / 16); 
                ctx.fillText(names[i], -ctx.measureText(names[i]).width / 2, 0);
                ctx.restore();
            }}
            ctx.restore();
        }}
        
        function animate(timestamp) {{
            if (!startTime) startTime = timestamp;
            const runtime = timestamp - startTime;
            
            if (runtime < duration) {{
                // Ease Out Quart formula
                const progress = runtime / duration;
                const ease = 1 - Math.pow(1 - progress, 4);
                
                startAngle = startRotation + (targetRotation - startRotation) * ease;
                drawWheel();
                requestAnimationFrame(animate);
            }} else {{
                startAngle = targetRotation;
                drawWheel();
                showResult();
            }}
        }}

        function showResult() {{
            if(targetWinner) {{
                document.getElementById('result').innerText = winnerLabel + " " + targetWinner;
            }}
        }}
        
        function spinTo(winnerName) {{
            if (isSpinning) return;
            isSpinning = true;
            
            let index = names.indexOf(winnerName);
            if (index === -1) index = 0;
            
            // MATH FIX:
            // 1. Canvas 0 is Top.
            // 2. Arrow is Right (+90 deg or +PI/2).
            // 3. Segment center is at (index * arc + arc/2).
            // 4. We want Segment Center to rotate to Arrow.
            //    SegmentPos + Rotation = ArrowPos
            //    Rotation = ArrowPos - SegmentPos
            
            const segmentCenter = index * arc + (arc/2);
            const arrowPos = Math.PI / 2; // 90 degrees (Right)
            
            // Add 10 full spins (20*PI) for effect
            const spins = 20 * Math.PI; 
            
            // Calculate final rotation needed
            const finalAngle = spins + (arrowPos - segmentCenter);
            
            startRotation = startAngle;
            targetRotation = finalAngle;
            
            startTime = null;
            requestAnimationFrame(animate);
        }}
        
        drawWheel();
        
        // Auto-start if target provided
        if (targetWinner) {{
            setTimeout(() => {{
                spinTo(targetWinner);
            }}, 500);
        }}
    </script>
    </body>
    </html>
    """
    
    components.html(html_code, height=600)
