import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
    return twMerge(clsx(inputs))
}

export function getPingColor(ping: number): string {
    if (ping > 120) return 'var(--red)';
    if (ping >= 90) return 'var(--orange)';
    return 'var(--neon-green)';
}
