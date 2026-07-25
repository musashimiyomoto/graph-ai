import type {
  NodePortSpec,
  PortCoercion,
  PortType,
} from './types'

const COERCIONS: Readonly<
  Partial<Record<`${PortType}:${PortType}`, PortCoercion>>
> = {
  'text:json': 'text_to_json',
  'json:text': 'json_to_text',
  'text:list': 'text_to_list',
  'list:text': 'list_to_text',
  'json:list': 'json_to_list',
  'list:json': 'list_to_json',
  'image:file': 'image_to_file',
  'audio:file': 'audio_to_file',
  'video:file': 'video_to_file',
}

export function resolvePortType(
  port: NodePortSpec | undefined,
  nodeData: Record<string, unknown>,
): PortType | null {
  if (!port) {
    return null
  }
  if (!port.type_field) {
    return port.type
  }
  const configured = nodeData[port.type_field]
  return typeof configured === 'string' &&
    port.allowed_types.includes(configured as PortType)
    ? (configured as PortType)
    : null
}

export function portForHandle(
  ports: NodePortSpec[],
  handle: string | null,
  routing = false,
): NodePortSpec | undefined {
  if (!handle || routing) {
    return ports[0]
  }
  return ports.find((port) => port.name === handle)
}

export function requiredPortCoercion(
  output: PortType,
  input: PortType,
): PortCoercion | null | undefined {
  if (output === input) {
    return null
  }
  return COERCIONS[`${output}:${input}`]
}

export function coercionLabel(coercion: PortCoercion): string {
  return coercion.replace('_to_', ' → ')
}
