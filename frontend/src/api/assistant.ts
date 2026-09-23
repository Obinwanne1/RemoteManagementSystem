import api from './client';

export interface AiMessage {
  id: string;
  conversation_id: string;
  role: 'user' | 'assistant' | 'tool';
  content: string;
  tool_calls: unknown;
  contains_warning: boolean;
  created_at: string | null;
}

export interface PendingAction {
  id: string;
  tool_name: string;
  summary: string;
  contains_warning: boolean;
  expires_at: string;
}

export interface ChatResponse {
  reply: string;
  suggested_actions: string[];
  contains_warning: boolean;
  conversation_id: string;
  pending_action?: PendingAction;
}

export interface ConversationResponse {
  conversation_id: string | null;
  messages: AiMessage[];
}

export function sendAssistantChat(message: string, page: string, context: Record<string, string | number>) {
  return api.post<ChatResponse>('/assistant/chat', { message, page, context }).then((r) => r.data);
}

export function getAssistantConversation() {
  return api.get<ConversationResponse>('/assistant/conversation').then((r) => r.data);
}

export function clearAssistantConversation() {
  return api.delete('/assistant/conversation').then((r) => r.data);
}

export function confirmAssistantAction(actionId: string) {
  return api.post(`/assistant/actions/${actionId}/confirm`).then((r) => r.data);
}

export function denyAssistantAction(actionId: string) {
  return api.post(`/assistant/actions/${actionId}/deny`).then((r) => r.data);
}
