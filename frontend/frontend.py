import streamlit as st
import requests
import json
import time
from typing import Dict, Any

# Page config
st.set_page_config(
    page_title="Idea2Repo",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Ultra-modern CSS styling
st.markdown("""
<style>
    /* Import modern fonts */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');
    
    /* Root variables */
    :root {
        --primary: #6366f1;
        --primary-dark: #4f46e5;
        --secondary: #8b5cf6;
        --accent: #06b6d4;
        --bg-primary: #0f0f23;
        --bg-secondary: #1a1a2e;
        --bg-tertiary: #16213e;
        --text-primary: #ffffff;
        --text-secondary: #a1a1aa;
        --border: #27272a;
        --success: #10b981;
        --error: #ef4444;
        --warning: #f59e0b;
    }
    
    /* Main app background */
    .stApp {
        background: var(--bg-primary);
        background-image: 
            radial-gradient(circle at 25% 25%, rgba(99, 102, 241, 0.1) 0%, transparent 50%),
            radial-gradient(circle at 75% 75%, rgba(139, 92, 246, 0.1) 0%, transparent 50%);
    }
    
    .main .block-container {
        padding: 2rem 1rem;
        max-width: 1400px;
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Typography */
    h1, h2, h3 {
        color: var(--text-primary) !important;
    }
    
    /* Text area styling */
    /* Fixed text area styling */
    .stTextArea textarea {
        background: var(--bg-tertiary) !important;
        border: 2px solid var(--border) !important;
        border-radius: 16px !important;
        color: var(--text-primary) !important;
        font-size: 16px !important;
        padding: 1.5rem !important;
        font-family: 'Inter', sans-serif !important;
        line-height: 1.6 !important;
        cursor: text !important;  /* Ensure cursor is text */
        user-select: text !important;  /* Ensure text selection works */
    }


    .stContainer > div {
        background: var(--bg-secondary);
        border: 1px solid var(--border);
        border-radius: 20px;
        padding: 2rem;
        margin-bottom: 2rem;
    }
    /* Only transition border color on focus */
    .stTextArea textarea:focus {
        border-color: var(--primary) !important;
        box-shadow: 0 0 0 4px rgba(99, 102, 241, 0.1) !important;
        outline: none !important;
    }

    
    
    /* Button styling */
    .stButton > button {
        background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%) !important;
        border: none !important;
        border-radius: 16px !important;
        padding: 1rem 2rem !important;
        font-weight: 600 !important;
        font-size: 16px !important;
        color: white !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 4px 20px rgba(99, 102, 241, 0.3) !important;
        min-height: 56px !important;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 8px 30px rgba(99, 102, 241, 0.4) !important;
    }
    
    /* Download button styling */
    .stDownloadButton > button {
        background: var(--bg-tertiary) !important;
        border: 2px solid var(--border) !important;
        color: var(--text-primary) !important;
        border-radius: 12px !important;
        padding: 1rem 1.5rem !important;
        font-weight: 600 !important;
        transition: all 0.3s ease !important;
        min-height: 56px !important;
    }
    
        .stDownloadButton > button:hover {
        border-color: var(--primary) !important;
        background: var(--primary) !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 20px rgba(99, 102, 241, 0.3) !important;
    }
    
    /* Alert styling */
    .stAlert > div {
        border-radius: 12px !important;
        padding: 1rem !important;
    }
    
    /* Expander styling */
    .streamlit-expanderHeader {
        background: var(--bg-tertiary) !important;
        border-radius: 12px !important;
        color: var(--text-primary) !important;
    }
    
    /* Code block styling */
    pre {
        background: #0d1117 !important;
        border: 1px solid #21262d !important;
        border-radius: 12px !important;
        padding: 1rem !important;
    }
    
    /* Custom containers */
    .app-header {
        text-align: center;
        padding: 3rem 0;
        margin-bottom: 2rem;
    }
    
    .app-title {
        font-size: 3.5rem;
        font-weight: 800;
        background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #06b6d4 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin-bottom: 0.5rem;
    }
    
    .app-subtitle {
        font-size: 1.25rem;
        color: var(--text-secondary);
        font-weight: 400;
    }
    
    .input-section {
        background: var(--bg-secondary);
        border: 1px solid var(--border);
        border-radius: 20px;
        padding: 2rem;
        margin-bottom: 2rem;
    }
    
    .repo-card {
        background: var(--bg-tertiary);
        border: 1px solid var(--border);
        border-radius: 16px;
        padding: 2rem;
        margin: 1.5rem 0;
    }
    
    .repo-name {
        font-size: 1.75rem;
        font-weight: 700;
        color: var(--text-primary);
        margin-bottom: 0.75rem;
    }
    
    .repo-desc {
        color: var(--text-secondary);
        font-size: 1.1rem;
        line-height: 1.6;
    }
    
    .readme-container {
        background: #0d1117;
        border: 1px solid #21262d;
        border-radius: 16px;
        padding: 2rem;
        margin: 1rem 0;
        color: #e6edf3;
        max-height: 600px;
        overflow-y: auto;
    }
</style>
""", unsafe_allow_html=True)

# Configuration
BACKEND_URL = "http://localhost:8000"

def stream_response(prompt: str) -> Dict[str, Any]:
    """Stream response from backend"""
    try:
        response = requests.post(
            f"{BACKEND_URL}/generate_repo/",
            json={"prompt": prompt},
            stream=True,
            timeout=60
        )
        response.raise_for_status()
        
        # Process the stream
        for line in response.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                if line_str.startswith('data: '):
                    try:
                        data = json.loads(line_str[6:])  # Remove 'data: '
                        if 'status' in data:
                            st.info(f"🤖 {data['message']}")
                        elif 'repository_name' in data:
                            return data
                    except json.JSONDecodeError:
                        continue
                        
        return None
        
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Connection error: {str(e)}")
        return None
    except Exception as e:
        st.error(f"❌ Unexpected error: {str(e)}")
        return None

def main():
    # Header
    st.markdown("""
    <div class="app-header">
        <h1 class="app-title">🚀 Idea2Repo</h1>
        <p class="app-subtitle">Get a head start on your next GitHub project</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Input section
    with st.container():
        st.markdown("### 💡 What do you want to build?")
    
        # Add visible instructions
        st.markdown("""
        <p style="color: #a1a1aa; font-size: 1rem; margin-bottom: 1rem; line-height: 1.5;">
        Describe your project idea in detail... e.g., <span style="color: #06b6d4; font-weight: 500;">
        A web app for tracking personal expenses with interactive charts, budget planning, 
        and receipt scanning features</span>
        </p>
        """, unsafe_allow_html=True)
    
        prompt = st.text_area(
        "",
        placeholder="Start typing your idea here...",  # Shorter placeholder
        height=120,
        help="Be specific about features, technologies, or requirements (5-500 characters)",
        key="prompt_input",
        label_visibility="collapsed"
    )

    
    # Character counter
    char_count = len(prompt) if prompt else 0
    color = "#22c55e" if 5 <= char_count <= 500 else "#ef4444" if char_count > 500 else "#64748b"
    st.markdown(f'<p style="text-align: right; color: {color}; font-size: 0.9rem; margin-top: 0.5rem;">{char_count}/500 characters</p>', unsafe_allow_html=True)

        
    

    
    # Create a centered column layout
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
    # Use nested columns to place buttons side-by-side
        btn_col1, btn_col2 = st.columns([1, 1])
    
    with btn_col1:
        generate_clicked = st.button("✨ Generate Repository", type="primary", use_container_width=True)
        
    with btn_col2:
        if st.button("✨ Push to Github", type="primary", use_container_width=True):
            # The button's action is to redirect, which is handled
            # by a simple HTML anchor tag
            auth_url = f"https://github.com/login/oauth/authorize?client_id={client_id}&scope=repo&redirect_uri={redirect_uri}"
            st.markdown(f'<a href="{auth_url}" target="_self">Click here to authorize with GitHub</a>', unsafe_allow_html=True)
    
    # Generation logic
    if generate_clicked:
        if not prompt.strip():
            st.error("❌ Please enter a project description")
            return
            
        if len(prompt.strip()) < 5:
            st.error("❌ Please provide a more detailed description (at least 5 characters)")
            return
        
        if len(prompt.strip()) > 500:
            st.error("❌ Description too long. Please keep it under 500 characters")
            return
        
        # Show loading with custom message
        with st.spinner("🤖 AI is crafting your repository... This may take a moment"):
            result = stream_response(prompt.strip())
        
        if result:
            st.success("✅ Repository generated successfully!")
            
            # Repository info card
            st.markdown(f"""
                        <div class="repo-card">
                <div class="repo-name">📁 {result['repository_name']}</div>
                <div class="repo-desc">{result['description']}</div>
            </div>
            """, unsafe_allow_html=True)
            
            # README preview
            st.markdown("### 📖 README.md Preview")
            
            # Clean up the readme content
            readme_content = result["readme_content"].replace("\\n", "\n")
            
            # Wrap the entire content in HTML
            st.markdown(f'''<div class="readme-container">{readme_content}</div>''', unsafe_allow_html=True)

            
            # # Display README in a container with markdown
            # with st.container():
            #     st.markdown('<div class="readme-container">', unsafe_allow_html=True)
            #     st.markdown(readme_content)
            #     st.markdown('</div>', unsafe_allow_html=True)
            
            
            # Download section
            st.markdown("### 📥 Download Files")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.download_button(
                    label="📄 README.md",
                    data=readme_content,
                    file_name="README.md",
                    mime="text/markdown",
                    use_container_width=True
                )
            
            with col2:
                st.download_button(
                    label="📋 Repository JSON",
                    data=json.dumps(result, indent=2),
                    file_name=f"{result['repository_name']}.json",
                    mime="application/json",
                    use_container_width=True
                )
            
            with col3:
                # Create a basic package.json if it's a web project
                if any(tech in result['description'].lower() for tech in ['web', 'react', 'node', 'javascript', 'app']):
                    package_json = {
                        "name": result['repository_name'],
                        "version": "1.0.0",
                        "description": result['description'],
                        "main": "index.js",
                        "scripts": {
                            "start": "node index.js",
                            "dev": "nodemon index.js"
                        },
                        "keywords": [],
                        "author": "",
                        "license": "MIT"
                    }
                    st.download_button(
                        label="📦 package.json",
                        data=json.dumps(package_json, indent=2),
                        file_name="package.json",
                        mime="application/json",
                        use_container_width=True
                    )
                else:
                    # For non-web projects, create a basic requirements.txt
                    requirements = "# Add your project dependencies here\n"
                    st.download_button(
                        label="📋 requirements.txt",
                        data=requirements,
                        file_name="requirements.txt",
                        mime="text/plain",
                        use_container_width=True
                    )
            
            

if __name__ == "__main__":
    main()
