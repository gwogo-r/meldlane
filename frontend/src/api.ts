const API_BASE = 'http://127.0.0.1:8000'

export interface TaskOut {
  id: string
  title: string
  status: string
  story_points: number | null
  assignee: string
  plane_id: string | null
}

export interface CapacityOut {
  member_id: string
  name: string
  kind: string
  story_points: number
  task_count: number
  tokens: number
  cost_usd_api: number
  cost_usd_subscription: number
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`)
  if (!res.ok) {
    throw new Error(`${path} -> HTTP ${res.status}`)
  }
  return res.json()
}

export const fetchTasks = () => getJson<TaskOut[]>('/api/tasks')
export const fetchCapacity = () => getJson<CapacityOut[]>('/api/capacity')
