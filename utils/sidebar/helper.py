import streamlit as st

# Update the side bar labels on the fly
def update_side_bar_labels():
	print("Updating side bar labels...")
	if not st.session_state.get("client_ready"):
		st.warning("Please Establish a connection to Weaviate on the side bar")
	else:
		st.sidebar.success(f'''Connection Status: Ready''')
		st.sidebar.markdown(f"Cluster Endpoint: {st.session_state.cluster_endpoint}")
		st.sidebar.markdown(f"### Versions")
		st.sidebar.html(f"Client: {st.session_state.client_version}<br />Server: {st.session_state.server_version}")
		print("cluster_endpoint in session state:", st.session_state.get('cluster_endpoint'))
		print("Server Version in session state:", st.session_state.get('server_version'))

# Clear the session state
def clear_session_state():
	print("Session state cleared!")
	for key in st.session_state.keys():
		del st.session_state[key]
