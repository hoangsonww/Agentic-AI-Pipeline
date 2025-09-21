pipeline {
  agent any
  environment {
    VENV = 'venv'
  }
  options { timestamps(); ansiColor('xterm'); disableConcurrentBuilds() }
  stages {
    stage('Checkout') {
      steps { checkout scm }
    }
    stage('Setup Python') {
      steps {
        sh '''
          python3 -m venv ${VENV}
          . ${VENV}/bin/activate
          python -m pip install -U pip
          pip install -r requirements.txt || true
          pip install ruff pytest
        '''
      }
    }
    stage('Lint') {
      steps {
        sh '''
          . ${VENV}/bin/activate
          ruff check src Agentic-Coding-Pipeline Agentic-RAG-Pipeline || true
        '''
      }
    }
    stage('Tests - Coding Pipeline') {
      steps {
        sh '''
          . ${VENV}/bin/activate
          pytest -q Agentic-Coding-Pipeline/tests
        '''
      }
    }
    stage('UI Smoke') {
      steps {
        sh '''
          . ${VENV}/bin/activate
          nohup python -m uvicorn agentic_ai.app:app --host 127.0.0.1 --port 8020 >/dev/null 2>&1 & echo $! > uvicorn.pid
          sleep 3
          set -eux
          curl -f http://127.0.0.1:8020/ | head -n 5
          curl -f http://127.0.0.1:8020/coding | head -n 5 || true
          curl -f http://127.0.0.1:8020/rag | head -n 5 || true
          kill $(cat uvicorn.pid) || true
        '''
      }
    }
  }
  post {
    always {
      archiveArtifacts artifacts: 'reports/**/*.xml', allowEmptyArchive: true
    }
  }
}

