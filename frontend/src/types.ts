// Type definitions for the Terminal companion interface

export interface Structure {
  id: string;
  system_name: string;
  owner_address: string;
  structure_name: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'ai' | 'system';
  text: string;
  timestamp: number;
}

export interface ConnectionState {
  isConnected: boolean;
  address: string | null;
  wallet: string | null;
}

export interface TerminalState {
  wallet: ConnectionState;
  selectedStructure: Structure | null;
  messages: ChatMessage[];
  isLoading: boolean;
  error: string | null;
}
