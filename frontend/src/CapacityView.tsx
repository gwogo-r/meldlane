import { useEffect, useState } from 'react'
import { fetchCapacity, type CapacityOut } from './api'

export function CapacityView() {
  const [rows, setRows] = useState<CapacityOut[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchCapacity().then(setRows).catch((e) => setError(String(e)))
  }, [])

  if (error) return <p className="error">{error}</p>
  if (!rows.length) return <p>нет данных</p>

  return (
    <table>
      <thead>
        <tr>
          <th>участник</th>
          <th>роль</th>
          <th>задач</th>
          <th>SP</th>
          <th>токены</th>
          <th>$ API</th>
          <th>$ подписка~</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.member_id}>
            <td>{r.name}</td>
            <td>{r.kind}</td>
            <td>{r.task_count}</td>
            <td>{r.story_points.toFixed(1)}</td>
            <td>{r.tokens}</td>
            <td>{r.cost_usd_api.toFixed(4)}</td>
            <td>{r.cost_usd_subscription.toFixed(4)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
