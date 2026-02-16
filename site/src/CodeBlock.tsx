import { useState } from 'react'
import { Highlight } from 'prism-react-renderer'

const beehiveTheme = {
  plain: {
    color: '#FFEF70',
    backgroundColor: '#2A2A2A',
  },
  styles: [
    {
      types: ['comment', 'prolog', 'doctype', 'cdata'],
      style: { color: '#6a6a6a', fontStyle: 'italic' as const },
    },
    {
      types: ['punctuation'],
      style: { color: '#888888' },
    },
    {
      types: ['property', 'tag', 'boolean', 'number', 'constant', 'symbol'],
      style: { color: '#FFEF70' },
    },
    {
      types: ['selector', 'attr-name', 'string', 'char', 'builtin'],
      style: { color: '#a8d4a8' },
    },
    {
      types: ['operator', 'entity', 'url'],
      style: { color: '#888888' },
    },
    {
      types: ['atrule', 'attr-value', 'keyword'],
      style: { color: '#c9a3ff' },
    },
    {
      types: ['function', 'class-name'],
      style: { color: '#FFEF70' },
    },
    {
      types: ['regex', 'important', 'variable'],
      style: { color: '#e8c97a' },
    },
  ],
}
import './CodeBlock.css'

interface CodeBlockProps {
  code: string
  language: string
  title?: string
}

export function CodeBlock({ code, language }: CodeBlockProps) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (err) {
      // Fallback for browsers that don't support clipboard API
      const textArea = document.createElement('textarea')
      textArea.value = code
      textArea.style.position = 'fixed'
      textArea.style.left = '-999999px'
      document.body.appendChild(textArea)
      textArea.select()
      try {
        document.execCommand('copy')
        setCopied(true)
        setTimeout(() => setCopied(false), 2000)
      } catch (fallbackErr) {
        console.error('Failed to copy code:', fallbackErr)
      }
      document.body.removeChild(textArea)
    }
  }

  return (
    <div className="code-block">
      <div className="code-block-container">
        <button
          className={`copy-button ${copied ? 'copied' : ''}`}
          onClick={handleCopy}
          aria-label="Copy code to clipboard"
        >
          {copied ? (
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path
                d="M13.5 4.5L6 12L2.5 8.5"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          ) : (
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <rect
                x="5.5"
                y="5.5"
                width="8"
                height="8"
                rx="1"
                stroke="currentColor"
                strokeWidth="1.5"
              />
              <path
                d="M3.5 10.5V3.5C3.5 2.94772 3.94772 2.5 4.5 2.5H11.5"
                stroke="currentColor"
                strokeWidth="1.5"
              />
            </svg>
          )}
        </button>
        <Highlight theme={beehiveTheme} code={code} language={language}>
          {({ className, style, tokens, getLineProps, getTokenProps }) => (
            <pre className={className} style={style}>
              {tokens.map((line, i) => (
                <div key={i} {...getLineProps({ line })}>
                  {line.map((token, key) => (
                    <span key={key} {...getTokenProps({ token })} />
                  ))}
                </div>
              ))}
            </pre>
          )}
        </Highlight>
      </div>
    </div>
  )
}
