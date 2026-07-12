import { useEffect, useState } from 'react'
import { fetchTasks, type TaskOut } from './api'

export function TasksView() {
  const [tasks, setTasks] = useState<TaskOut[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchTasks().then(setTasks).catch((e) => setError(String(e)))
  }, [])

  if (error) return <p className="error">{error}</p>
  if (!tasks.length) return <p>нет задач</p>

  return (
    <table>
      <thead>
        <tr>
          <th>title</th>
          <th>status</th>
          <th>SP</th>
          <th>assignee</th>
        </tr>
      </thead>
      <tbody>
        {tasks.map((t) => (
          <tr key={t.id}>
            <td>{t.title}</td>
            <td>{t.status}</td>
            <td>{t.story_points ?? '—'}</td>
            <td>{t.assignee}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
