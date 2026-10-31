export interface LoginPayload {
  organization_slug: string;
  email: string;
  password: string;
  remember_me?: boolean;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface DemoStatus {
  enabled: boolean;
  account_name?: string;
  organization_name?: string;
  read_only?: boolean;
}

export interface RegisterPayload {
  full_name: string;
  organization_name: string;
  organization_slug: string;
  email: string;
  password: string;
}

export interface Me {
  id: string;
  full_name: string;
  email: string;
  organization_id: string;
  organization_name: string;
  organization_slug: string;
  role: string;
  demo_mode?: boolean;
  demo_read_only?: boolean;
}
