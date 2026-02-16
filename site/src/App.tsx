import './App.css'

function App() {
  return (
    <div className="app">
      <header className="header">
        <div className="logo">bh</div>
      </header>

      <main className="main-content">
        <div className="content-container">
          <h1 className="title">Beehive</h1>
          <p className="description">
            An AI-powered development tool that helps you build better software faster.
            Beehive combines the power of Claude AI with seamless development workflows
            to help you architect, plan, and implement features with confidence.
          </p>

          <div className="features">
            <div className="feature">
              <h3>🤖 AI-Powered Architecture</h3>
              <p>Let Claude help you design and plan your implementation strategies</p>
            </div>
            <div className="feature">
              <h3>📝 Smart Planning</h3>
              <p>Break down complex tasks into manageable, well-structured plans</p>
            </div>
            <div className="feature">
              <h3>⚡ Seamless Workflow</h3>
              <p>Integrate AI assistance directly into your development process</p>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}

export default App
