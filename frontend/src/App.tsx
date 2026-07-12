import { useState } from 'react'
import './App.css'
import { TasksView } from './TasksView'
import { CapacityView } from './CapacityView'

type Tab = 'tasks' | 'capacity'

function App() {
  const [tab, setTab] = useState<Tab>('tasks')

  return (
    <main>
      <h1>Meldlane</h1>
      <nav>
        <button className={tab === 'tasks' ? 'active' : ''} onClick={() => setTab('tasks')}>
          Задачи
        </button>
        <button className={tab === 'capacity' ? 'active' : ''} onClick={() => setTab('capacity')}>
          Capacity
        </button>
      </nav>
      {tab === 'tasks' ? <TasksView /> : <CapacityView />}
    </main>
  )
}

export default App
