import './App.css'
import { CodeBlock } from './CodeBlock'

function App() {
  return (
    <div className="app-container">
      <header>
        <div className="logo">bh 🐝</div>
      </header>

      <main>
        {/* Motto Section */}
        <p className="summary">
          Beehive is an opinionated tool for building and orchestrating complex technical projects with agents.
          </p>
          <ul className="summary-bullets">
            <li>Agents run in isolated containers and create a PR for a ticket (either part of a Plan or ad hoc).</li>
            <li>Architects create Plans for complex technical projects, a directed graph of tickets that can be executed sequentially or in parallel.  Each plan creates its own feature branch and presents a preview environment for the project.</li>
            <li>Research scientists run experiments using an repo, log to w&b and is SLURM native</li>
            <li>Autopilot CTO mode creates a roadmap for a broad strategic vision of projects.</li>
          </ul>
        <p className="buzz-motto">
          Buzz buzz, that’s the sound of your cpus & gpus humming along while you sleep and you live your life
        </p>

        <section className="content-section">
          <h4>Installation</h4>
          <p>Install Beehive using Homebrew:</p>
          <CodeBlock
            code="brew tap sanjeev-/beehive\nbrew install beehive"
            language="bash"
            title="Install via Homebrew"
          />
        </section>

        <section className="content-section">
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
      </main>
    </div>
  )
}

export default App