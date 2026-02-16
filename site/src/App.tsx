import './App.css'
import { CodeBlock } from './CodeBlock'

function App() {
  return (
    <div className="app-wrapper">
      <header className="header">
        <div className="logo">bh 🐝</div>
      </header>

      <main className="main-content">
        {/* New Motto Section */}
        <p className="motto">
          Buzz buzz, that’s the sound of your cpus & gpus humming along while you sleep and you live your life
        </p>

        <h1 className="title">Beehive</h1>
        <section className="installation-section">
          <h2>Installation</h2>
          <p>Install Beehive using Homebrew:</p>
          <CodeBlock
            code="brew tap sanjeev-/beehive\nbrew install beehive"
            language="bash"
            title="Install via Homebrew"
          />
        </section>

        <section className="usage-section">
          <h2>Getting Started</h2>
          <p>Create a new development session:</p>
          <CodeBlock
            code="beehive session create"
            language="bash"
            title="Create a session"
          />

          <p>Plan your implementation with AI assistance:</p>
          <CodeBlock
            code="beehive architect plan"
            language="bash"
            title="Create a plan"
          />

          <p>Watch and implement your plan in real-time:</p>
          <CodeBlock
            code="beehive architect watch"
            language="bash"
            title="Watch mode"
          />
        </section>
      </main>
    </div>
  )
}

export default App