'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuth } from '@/context/AuthContext';
import { getPingColor } from '@/lib/utils';

const NAV_ITEMS = [
    { href: '/', icon: '🎮', label: 'Mixer & Draft' },
    { href: '/stats', icon: '📊', label: 'Stats' },
    { href: '/trophies', icon: '🏆', label: 'Trophies' },
    { href: '/history', icon: '📜', label: 'History' },
    { href: '/wheel', icon: '🎡', label: 'Bench Wheel' },
    { href: '/admin', icon: '⚙️', label: 'Admin' },
];

export default function Sidebar() {
    const pathname = usePathname();
    const { user } = useAuth();

    // Hide sidebar on mobile vote pages
    if (pathname.startsWith('/vote')) return null;

    return (
        <aside className="sidebar">
            <div className="sidebar-header">
                <Link href="/" className="sidebar-logo">
                    <span className="sidebar-logo-icon">⚡</span>
                    <span className="sidebar-logo-text">UNBALANCED</span>
                </Link>
            </div>

            <nav className="sidebar-nav">
                {NAV_ITEMS.map((item) => {
                    const isActive = pathname === item.href ||
                        (item.href !== '/' && pathname.startsWith(item.href));

                    return (
                        <Link
                            key={item.href}
                            href={item.href}
                            className={`nav-item ${isActive ? 'active' : ''}`}
                        >
                            <span className="nav-item-icon">{item.icon}</span>
                            <span className="nav-item-label">{item.label}</span>
                        </Link>
                    );
                })}
            </nav>

            {/* Live Draft Indicator */}
            {user?.in_draft && (
                <div style={{ padding: '0 12px', marginBottom: 12 }}>
                    <Link
                        href="/profile?tab=live"
                        className={`nav-item ${pathname === '/profile' ? 'active' : ''}`}
                        style={{
                            background: 'rgba(255, 0, 0, 0.1)',
                            border: '1px solid rgba(255, 0, 0, 0.3)',
                            color: 'var(--red)',
                            animation: 'pulse 2s infinite'
                        }}
                    >
                        <span className="nav-item-icon">{user.is_captain ? '👑' : '🔴'}</span>
                        <span className="nav-item-label" style={{ fontWeight: 700 }}>Live Draft</span>
                    </Link>
                </div>
            )}

            {/* Auth section */}
            <div style={{ padding: '16px 12px', borderTop: '1px solid var(--border)', marginTop: 'auto' }}>
                {user ? (
                    <Link
                        href="/profile"
                        className={`nav-item ${pathname === '/profile' ? 'active' : ''}`}
                        style={{ marginBottom: 0 }}
                    >
                        <span style={{
                            width: 28, height: 28, borderRadius: '50%',
                            background: user.role === 'admin' ? 'linear-gradient(135deg, var(--gold), #ff8c00)' : 'linear-gradient(135deg, var(--neon-green), #00a0ff)',
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            fontSize: 12, fontWeight: 800, color: '#000', flexShrink: 0,
                        }}>
                            {user.display_name[0]?.toUpperCase()}
                        </span>
                        <span className="nav-item-label" style={{ fontWeight: 600 }}>
                            {user.display_name}
                            {user.ping && (
                                <span style={{ fontSize: 10, color: getPingColor(user.ping), marginLeft: 6, fontWeight: 400 }}>
                                    {user.ping}ms
                                </span>
                            )}
                        </span>
                    </Link>
                ) : (
                    <Link
                        href="/login"
                        className={`nav-item ${pathname === '/login' ? 'active' : ''}`}
                        style={{ marginBottom: 0 }}
                    >
                        <span className="nav-item-icon">🔑</span>
                        <span className="nav-item-label">Sign In</span>
                    </Link>
                )}
            </div>

            <div className="sidebar-footer">
                CS2 Pro Balancer v2.0
            </div>
        </aside>
    );
}
