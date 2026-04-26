// Tiny shared helper for calling the Anthropic API from edge functions.
// Pulls ANTHROPIC_API_KEY from secrets. No SDK import — direct REST.

const API_URL = 'https://api.anthropic.com/v1/messages';
const VERSION = '2023-06-01';

export type AnthropicModel =
  | 'claude-haiku-4-5'           // cheap, fast — classification
  | 'claude-sonnet-4-5'          // best balance — vision, reasoning
  | 'claude-opus-4-5';           // overkill for our use cases

export type Msg = {
  role: 'user' | 'assistant';
  content: string | Array<{ type: 'text'; text: string } | { type: 'image'; source: any }>;
};

export async function chat(opts: {
  model: AnthropicModel;
  system?: string;
  messages: Msg[];
  maxTokens?: number;
  temperature?: number;
}): Promise<{ text: string; usage?: any } | { error: string }> {
  const key = Deno.env.get('ANTHROPIC_API_KEY') ?? '';
  if (!key) return { error: 'ANTHROPIC_API_KEY not set' };

  const body: any = {
    model: opts.model,
    max_tokens: opts.maxTokens ?? 1024,
    messages: opts.messages,
  };
  if (opts.system) body.system = opts.system;
  if (opts.temperature != null) body.temperature = opts.temperature;

  try {
    const r = await fetch(API_URL, {
      method: 'POST',
      headers: {
        'x-api-key': key,
        'anthropic-version': VERSION,
        'content-type': 'application/json',
      },
      body: JSON.stringify(body),
    });
    const json = await r.json();
    if (!r.ok) return { error: json?.error?.message ?? `HTTP ${r.status}` };
    const text =
      json?.content
        ?.map((c: any) => (c?.type === 'text' ? c.text : ''))
        .join('') ?? '';
    return { text, usage: json?.usage };
  } catch (e) {
    return { error: String(e) };
  }
}
