'use client';
import { useState, useEffect, useRef, useCallback } from 'react';
import { getPlayers } from '../lib/api';

const COLORS = ['#FF0000', '#00FF00', '#0000FF', '#FFFF00', '#FF00FF', '#00FFFF', '#FFA500', '#800080', '#008080', '#FFC0CB'];

export default function WheelPage() {
    const [names, setNames] = useState<string[]>([]);
    const [newName, setNewName] = useState('');
    const [winner, setWinner] = useState('');
    const [spinning, setSpinning] = useState(false);
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const angleRef = useRef(0);
    const animRef = useRef<number | null>(null);

    useEffect(() => {
        getPlayers().then(p => setNames(p.map((x: { name: string }) => x.name))).catch(() => { });
    }, []);

    const drawWheel = useCallback(() => {
        const canvas = canvasRef.current;
        if (!canvas || names.length === 0) return;
        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        const size = 600;
        const center = size / 2;
        const radius = size / 2 - 20;
        const arc = (2 * Math.PI) / names.length;

        ctx.clearRect(0, 0, size, size);
        ctx.save();
        ctx.translate(center, center);
        ctx.rotate(angleRef.current);

        for (let i = 0; i < names.length; i++) {
            const angle = i * arc;
            ctx.fillStyle = COLORS[i % COLORS.length];
            ctx.beginPath();
            ctx.arc(0, 0, radius, angle, angle + arc, false);
            ctx.arc(0, 0, 0, angle + arc, angle, true);
            ctx.fill();

            ctx.save();
            ctx.fillStyle = '#000';
            ctx.font = 'bold 20px Arial';
            ctx.translate(
                Math.cos(angle + arc / 2) * (radius - 80),
                Math.sin(angle + arc / 2) * (radius - 80)
            );
            ctx.rotate(angle + arc / 2 + Math.PI / 16);
            ctx.fillText(names[i], -ctx.measureText(names[i]).width / 2, 0);
            ctx.restore();
        }
        ctx.restore();
    }, [names]);

    useEffect(() => { drawWheel(); }, [drawWheel]);

    const spin = () => {
        if (spinning || names.length === 0) return;
        setSpinning(true);
        setWinner('');

        const winnerIdx = Math.floor(Math.random() * names.length);
        const arc = (2 * Math.PI) / names.length;
        const segmentCenter = winnerIdx * arc + arc / 2;
        const arrowPos = Math.PI / 2;
        const spins = 20 * Math.PI;
        const finalAngle = spins + (arrowPos - segmentCenter);

        const startAngle = angleRef.current;
        const startTime = performance.now();
        const duration = 6000;

        const animate = (timestamp: number) => {
            const runtime = timestamp - startTime;
            if (runtime < duration) {
                const progress = runtime / duration;
                const ease = 1 - Math.pow(1 - progress, 4);
                angleRef.current = startAngle + (finalAngle - startAngle) * ease;
                drawWheel();
                animRef.current = requestAnimationFrame(animate);
            } else {
                angleRef.current = finalAngle;
                drawWheel();
                setWinner(names[winnerIdx]);
                setSpinning(false);
            }
        };

        animRef.current = requestAnimationFrame(animate);
    };

    const removePlayer = (name: string) => {
        setNames(prev => prev.filter(n => n !== name));
        if (winner === name) setWinner('');
    };

    const addPlayer = () => {
        if (newName.trim() && !names.includes(newName.trim())) {
            setNames(prev => [...prev, newName.trim()]);
            setNewName('');
        }
    };

    return (
        <div className="page-container">
            <div className="page-header">
                <h1 className="page-title">🎡 Bench Wheel</h1>
                <p className="page-subtitle">Spin the wheel to pick or bench a player</p>
            </div>

            <div className="grid-2" style={{ alignItems: 'start' }}>
                {/* Wheel */}
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                    <div className="wheel-container">
                        <div className="wheel-arrow" />
                        <canvas
                            ref={canvasRef}
                            width={600}
                            height={600}
                            className="wheel-canvas"
                        />
                    </div>

                    {winner && (
                        <div className="wheel-winner">
                            🎉 {winner}
                        </div>
                    )}

                    <button
                        className="btn btn-primary"
                        onClick={spin}
                        disabled={spinning || names.length === 0}
                        style={{ marginTop: 20, fontSize: 18, padding: '14px 48px' }}
                    >
                        {spinning ? '⏳ Spinning...' : '🎰 SPIN'}
                    </button>
                </div>

                {/* Player list */}
                <div className="card">
                    <div className="card-header">Players in Wheel ({names.length})</div>

                    <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
                        <input className="input" value={newName} onChange={e => setNewName(e.target.value)} placeholder="Add player..." onKeyDown={e => e.key === 'Enter' && addPlayer()} />
                        <button className="btn btn-sm" onClick={addPlayer}>Add</button>
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 400, overflowY: 'auto' }}>
                        {names.map(n => (
                            <div key={n} className="player-chip" style={{ justifyContent: 'space-between' }}>
                                <span style={{ fontWeight: winner === n ? 800 : 500, color: winner === n ? 'var(--neon-green)' : undefined }}>
                                    {winner === n && '🏆 '}{n}
                                </span>
                                <button className="btn btn-sm btn-danger" onClick={() => removePlayer(n)} style={{ padding: '4px 10px' }}>✕</button>
                            </div>
                        ))}
                    </div>

                    <div className="divider" />
                    <button className="btn btn-sm btn-block" onClick={() => getPlayers().then(p => setNames(p.map((x: { name: string }) => x.name)))}>
                        🔄 Reset to All Players
                    </button>
                </div>
            </div>
        </div>
    );
}
