import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

export function middleware(request: NextRequest) {
    const token = request.cookies.get('token')?.value

    // Protected Routes
    if (request.nextUrl.pathname.startsWith('/profile') || request.nextUrl.pathname.startsWith('/dashboard')) {
        if (!token) {
            return NextResponse.redirect(new URL('/login', request.url))
        }
    }

    // Auth Routes (Guest only)
    if (request.nextUrl.pathname.startsWith('/login') || request.nextUrl.pathname.startsWith('/register')) {
        if (token) {
            return NextResponse.redirect(new URL('/profile', request.url)) // Redirect to profile/dashboard
        }
    }

    return NextResponse.next()
}

export const config = {
    matcher: ['/profile/:path*', '/dashboard/:path*', '/login', '/register'],
}
