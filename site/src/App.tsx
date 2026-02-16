import './App.css'
import { CodeBlock } from './CodeBlock'

function App() {
  return (
    <div className="app">
      <header className="header">
        <div className="logo">bh 🐝</div>
      </header>

      <main className="usage-section">
        <div className="content-container">
        <section className="buzz-section">
          <p>Buzz buzz, that’s the sound of your cpus & gpus humming along while you sleep and you live your life</p>
        </section>
          <section className="installation-section">
            <h4>Installation</h4>
            <p>Install Beehive using Homebrew:</p>
            <CodeBlock
              code="brew tap sanjeev-/beehive\nbrew install beehive"
              language="bash"
              title="Install via Homebrew"
            />
          </section>

          <section className="usage-section">
            <h4>Getting Started</h4>
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
        </div>
      </main>
    </div>
  )
}

export default App
