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
          Beehive is an opinionated tool for building complex technical projects with semi-autonomous agents.
          </p>
          <ul className="summary-bullets">
            <li><b>Agents</b> run in isolated containers and create a PR for review.</li>
            <li><b>Architects</b> implement complex technical projects, creating a feature branch and presenting a preview environment for review.</li>
            <li><b>Researchers</b> run experiments, ablations, profiling and benchmarks for ML projects.  They output a RESULTS.md file and a Latex formatted report.</li>
            <li><b>Strategists</b> create a roadmap for a broad strategic vision of projects and automates the execution of the roadmap.</li>
          </ul>
        <p className="buzz-motto">
          Buzz buzz, that’s the sound of your cpus & gpus humming along while you sleep and you live your life
        </p>

        <section className="content-section">
          <h4>Installation</h4>
          <p>Install with a single command:</p>
          <CodeBlock
            code="curl -fsSL http://beehive-site.s3-website-us-east-1.amazonaws.com/install.sh | bash"
            language="bash"
          />
        </section>

        <section className="content-section">
          <h4>Getting Started</h4>
          <p>Create a new development session:</p>
          <CodeBlock
            code="beehive session create"
            language="bash"
          />

          <p>Plan your implementation with AI assistance:</p>
          <CodeBlock
            code="beehive architect plan"
            language="bash"
          />

          <p>Watch and implement your plan in real-time:</p>
          <CodeBlock
            code="beehive architect watch"
            language="bash"
          />
          <p>Terminal UI for monitoring and managing your plan:</p>
          <CodeBlock
            code="beehive ui"
            language="bash"
          />          
        </section>
      </main>
    </div>
  )
}

export default App