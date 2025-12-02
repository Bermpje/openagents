/**
 * Event Explorer Service
 * Fetches and parses event definitions from GitHub repository
 */

import * as yaml from 'js-yaml';

export interface EventDefinition {
  eventName: string;
  address: string;
  type: 'operation' | 'response' | 'notification';
  description: string;
  mod: string;
  sourceFile: string;
  requestPayload?: SchemaDefinition;
  responsePayload?: SchemaDefinition;
  payload?: SchemaDefinition;
  relatedEvents?: string[];
  operationSummary?: string;
}

export interface SchemaDefinition {
  type?: string;
  properties?: Record<string, SchemaProperty>;
  required?: string[];
  items?: SchemaDefinition;
  example?: any;
}

export interface SchemaProperty {
  type?: string;
  description?: string;
  default?: any;
  example?: any;
  items?: SchemaDefinition;
  enum?: any[];
}

interface AsyncAPIDefinition {
  asyncapi: string;
  info: {
    title: string;
    version: string;
    description?: string;
  };
  channels: Record<string, ChannelDefinition>;
  operations?: Record<string, OperationDefinition>;
  components?: {
    messages?: Record<string, MessageDefinition>;
    schemas?: Record<string, SchemaDefinition>;
  };
}

interface ChannelDefinition {
  address: string;
  description?: string;
  messages?: Record<string, MessageReference>;
}

interface MessageReference {
  $ref?: string;
}

interface OperationDefinition {
  action: 'send' | 'receive';
  channel: {
    $ref: string;
  };
  summary?: string;
}

interface MessageDefinition {
  name?: string;
  title?: string;
  summary?: string;
  contentType?: string;
  x_event_type?: 'operation' | 'response' | 'notification';
  payload?: SchemaDefinition | { $ref: string };
}

const GITHUB_REPO = 'openagents-org/openagents';
const GITHUB_BRANCH = 'main';
const GITHUB_API_BASE = 'https://api.github.com';

/**
 * Fetch raw file content from GitHub
 */
async function fetchGitHubFile(path: string): Promise<string> {
  const url = `https://raw.githubusercontent.com/${GITHUB_REPO}/${GITHUB_BRANCH}/${path}`;
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to fetch ${path}: ${response.statusText}`);
  }
  return response.text();
}

/**
 * Find all eventdef.yaml files in the repository
 */
async function findEventDefinitionFiles(): Promise<string[]> {
  try {
    // Use GitHub API to search for eventdef.yaml files
    const searchUrl = `${GITHUB_API_BASE}/search/code?q=filename:eventdef.yaml+repo:${GITHUB_REPO}`;
    const response = await fetch(searchUrl);
    
    if (!response.ok) {
      // Fallback: use known paths if API fails
      return [
        'src/openagents/mods/core/shared_cache/eventdef.yaml',
        'src/openagents/mods/workspace/documents/eventdef.yaml',
        'src/openagents/mods/workspace/forum/eventdef.yaml',
        'src/openagents/mods/workspace/messaging/eventdef.yaml',
        'src/openagents/mods/workspace/project/eventdef.yaml',
        'src/openagents/mods/workspace/feed/eventdef.yaml',
      ];
    }
    
    const data = await response.json();
    return data.items?.map((item: any) => item.path) || [];
  } catch (error) {
    console.warn('Failed to search GitHub, using fallback paths:', error);
    // Fallback to known paths
    return [
      'src/openagents/mods/core/shared_cache/eventdef.yaml',
      'src/openagents/mods/workspace/documents/eventdef.yaml',
      'src/openagents/mods/workspace/forum/eventdef.yaml',
      'src/openagents/mods/workspace/messaging/eventdef.yaml',
      'src/openagents/mods/workspace/project/eventdef.yaml',
      'src/openagents/mods/workspace/feed/eventdef.yaml',
    ];
  }
}

/**
 * Parse YAML content using js-yaml
 */
function parseYAML(content: string): any {
  try {
    return yaml.load(content);
  } catch (error) {
    console.error('YAML parsing error:', error);
    throw error;
  }
}

/**
 * Extract mod name from file path
 */
function extractModName(filePath: string): string {
  const parts = filePath.split('/');
  // Extract mod name from path like: src/openagents/mods/core/shared_cache/eventdef.yaml
  // or src/openagents/mods/workspace/documents/eventdef.yaml
  if (parts.includes('core')) {
    const modIndex = parts.indexOf('core');
    return parts[modIndex + 1] || 'unknown';
  } else if (parts.includes('workspace')) {
    const modIndex = parts.indexOf('workspace');
    return parts[modIndex + 1] || 'unknown';
  }
  return 'unknown';
}

/**
 * Resolve schema reference
 */
function resolveSchemaRef(
  ref: string,
  components: AsyncAPIDefinition['components']
): SchemaDefinition | undefined {
  if (!ref.startsWith('#/components/schemas/')) {
    return undefined;
  }
  
  const schemaName = ref.split('/').pop();
  return components?.schemas?.[schemaName || ''];
}

/**
 * Resolve message reference
 */
function resolveMessageRef(
  ref: string,
  components: AsyncAPIDefinition['components']
): MessageDefinition | undefined {
  if (!ref.startsWith('#/components/messages/')) {
    return undefined;
  }
  
  const messageName = ref.split('/').pop();
  return components?.messages?.[messageName || ''];
}

/**
 * Extract schema information
 */
function extractSchema(schema: SchemaDefinition | { $ref: string } | undefined, components: AsyncAPIDefinition['components']): SchemaDefinition | undefined {
  if (!schema) return undefined;
  
  if ('$ref' in schema) {
    return resolveSchemaRef(schema.$ref, components);
  }
  
  return schema as SchemaDefinition;
}

/**
 * Parse event definitions from AsyncAPI definition
 */
function parseEventDefinitions(
  definition: AsyncAPIDefinition,
  sourceFile: string
): EventDefinition[] {
  const events: EventDefinition[] = [];
  const mod = extractModName(sourceFile);
  const channels = definition.channels || {};
  const components = definition.components || {};
  const operations = definition.operations || {};
  
  // Build operation map for finding related events
  const operationMap: Record<string, OperationDefinition> = {};
  Object.entries(operations).forEach(([key, op]) => {
    if (op.channel?.$ref) {
      const channelRef = op.channel.$ref.replace('#/channels/', '');
      operationMap[channelRef] = op;
    }
  });
  
  // Process each channel
  Object.entries(channels).forEach(([channelKey, channel]) => {
    const address = channel.address;
    if (!address) return;
    
    // Get messages for this channel
    const channelMessages = channel.messages || {};
    
    Object.entries(channelMessages).forEach(([msgKey, msgRef]) => {
      let messageDef: MessageDefinition | undefined;
      
      if (msgRef.$ref) {
        messageDef = resolveMessageRef(msgRef.$ref, components);
      }
      
      if (!messageDef) return;
      
      const eventType = messageDef.x_event_type || 
        (address.includes('.response') ? 'response' :
         address.includes('.notification') || address.includes('notification.') ? 'notification' :
         'operation');
      
      // Extract payload schema
      const payload = extractSchema(messageDef.payload, components);
      
      // Find related events
      const relatedEvents: string[] = [];
      if (eventType === 'operation') {
        // Find corresponding response
        const responseAddress = `${address}.response`;
        if (Object.values(channels).some(c => c.address === responseAddress)) {
          relatedEvents.push(responseAddress);
        }
        // Find corresponding notification
        const notificationAddress = address.replace(/\.(create|update|delete|get|list|save|rename)/, '.notification.$1ed');
        if (Object.values(channels).some(c => c.address === notificationAddress)) {
          relatedEvents.push(notificationAddress);
        }
      }
      
      // Find operation summary
      const operationSummary = Object.values(operations).find(op => {
        if (op.channel?.$ref) {
          const refChannel = op.channel.$ref.replace('#/channels/', '');
          return refChannel === channelKey;
        }
        return false;
      })?.summary;
      
      const event: EventDefinition = {
        eventName: messageDef.name || address,
        address,
        type: eventType as 'operation' | 'response' | 'notification',
        description: messageDef.summary || channel.description || messageDef.title || 'No description',
        mod,
        sourceFile,
        relatedEvents: relatedEvents.length > 0 ? relatedEvents : undefined,
        operationSummary,
      };
      
      if (eventType === 'operation') {
        event.requestPayload = payload;
        // Try to find response payload
        const responseAddress = `${address}.response`;
        const responseChannel = Object.values(channels).find(c => c.address === responseAddress);
        if (responseChannel) {
          const responseMessages = responseChannel.messages || {};
          const responseMsgRef = Object.values(responseMessages)[0];
          if (responseMsgRef?.$ref) {
            const responseMsg = resolveMessageRef(responseMsgRef.$ref, components);
            if (responseMsg) {
              event.responsePayload = extractSchema(responseMsg.payload, components);
            }
          }
        }
      } else if (eventType === 'notification') {
        event.payload = payload;
      } else if (eventType === 'response') {
        event.responsePayload = payload;
      }
      
      events.push(event);
    });
  });
  
  return events;
}

/**
 * Fetch and parse all event definitions
 */
export async function fetchAllEventDefinitions(): Promise<EventDefinition[]> {
  try {
    const filePaths = await findEventDefinitionFiles();
    const allEvents: EventDefinition[] = [];
    
    for (const filePath of filePaths) {
      try {
        const content = await fetchGitHubFile(filePath);
        const definition = await parseYAMLWithFallback(content);
        
        if (definition && definition.asyncapi) {
          const events = parseEventDefinitions(definition, filePath);
          allEvents.push(...events);
        }
      } catch (error) {
        console.error(`Failed to parse ${filePath}:`, error);
      }
    }
    
    return allEvents;
  } catch (error) {
    console.error('Failed to fetch event definitions:', error);
    throw error;
  }
}

/**
 * Parse YAML with fallback methods
 */
async function parseYAMLWithFallback(content: string): Promise<AsyncAPIDefinition | null> {
  try {
    return parseYAML(content) as AsyncAPIDefinition;
  } catch (error) {
    console.error('Failed to parse YAML:', error);
    return null;
  }
}

/**
 * Get all unique mods from events
 */
export function getModsFromEvents(events: EventDefinition[]): string[] {
  const mods = new Set(events.map(e => e.mod));
  return Array.from(mods).sort();
}

/**
 * Filter events by mod
 */
export function filterEventsByMod(events: EventDefinition[], mod: string): EventDefinition[] {
  if (!mod || mod === 'all') return events;
  return events.filter(e => e.mod === mod);
}

/**
 * Filter events by type
 */
export function filterEventsByType(events: EventDefinition[], type: string): EventDefinition[] {
  if (!type || type === 'all') return events;
  return events.filter(e => e.type === type);
}

/**
 * Search events by query
 */
export function searchEvents(events: EventDefinition[], query: string): EventDefinition[] {
  if (!query) return events;
  
  const lowerQuery = query.toLowerCase();
  return events.filter(event => 
    event.eventName.toLowerCase().includes(lowerQuery) ||
    event.address.toLowerCase().includes(lowerQuery) ||
    event.description.toLowerCase().includes(lowerQuery) ||
    event.mod.toLowerCase().includes(lowerQuery)
  );
}
