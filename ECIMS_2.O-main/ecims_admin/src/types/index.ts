export interface LoginResponse { access_token: string; token_type: string }
export interface User { id: number; username: string; role: string; is_active: boolean }
export interface Agent { id: number; hostname: string; name: string; last_seen: string; status: string; device_mode_override?: string }
export interface Alert { id: number; severity: 'RED' | 'YELLOW' | 'GREEN' | string; alert_type: string; message: string; ts: string; status: string }
