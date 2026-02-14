'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuth } from '@/context/AuthContext';
import { getPingColor } from '@/lib/utils';

const NAV_ITEMS = [
    { href: '/', icon: '🎮', label: 'Mixer & Draft' },
    { href: '/tournaments', icon: '🏟️', label: '1v1 Tournaments' },
    { href: '/stats', icon: '📊', label: 'Stats' },
    { href: '/trophies', icon: '🏆', label: 'Trophies' },
    { href: '/history', icon: '📜', label: 'History' },
    { href: '/wheel', icon: '🎡', label: 'Bench Wheel' },
    { href: '/admin', icon: '⚙️', label: 'Admin' },
];

export default function Sidebar() {
    const pathname = usePathname();
    const { user } = useAuth();

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

            {user?.in_draft && (
                <div style={{ padding: '0 12px', marginBottom: 12 }}>
                    <Link
                        href="/captain"
                        className={`nav-item live-draft-indicator ${pathname === '/captain' ? 'active' : ''}`}
                    >
                        <span className="nav-item-icon">{user.is_captain ? '👑' : '🔴'}</span>
                        <span className="nav-item-label" style={{ fontWeight: 700 }}>Live Draft</span>
                    </Link>
                </div>
            )}

            <div className="sidebar-user-section">
                {user ? (
                    <Link
                        href="/profile"
                        className={`nav-item ${pathname === '/profile' ? 'active' : ''}`}
                    >
                        <span className={`user-avatar ${user.role === 'admin' ? 'user-avatar-admin' : 'user-avatar-user'}`}>
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
