import streamlit as st
import json
from datetime import datetime, date
from utils.objects.update_object import get_object_in_collection, display_object_as_table, find_object_in_collection_on_nodes, get_object_in_tenant, find_object_in_tenant_on_nodes, update_object_properties
from utils.collections.update_collection_config import get_collection_config, update_description_and_inverted_index, update_multi_tenancy_and_replication, update_hnsw_vector_index, update_pq_quantizer
from utils.sidebar.navigation import navigate
from utils.sidebar.helper import update_side_bar_labels
from utils.cluster.collection import fetch_collection_config, list_collections
from utils.page_config import set_custom_page_config
from weaviate.classes.config import PQEncoderType, PQEncoderDistribution, VectorFilterStrategy, StopwordsPreset

# Function to map schema properties to their types
def build_type_map_from_schema(schema):
	print(f"build_type_map_from_schema called")
	type_map = {}
	for prop in schema.get('properties', []):
		name = prop.get('name')
		data_type = prop.get('dataType', [])
		# Handle array types
		if isinstance(data_type, list) and len(data_type) == 1:
			dt = data_type[0]
			if dt.endswith('[]'):
				base_type = dt[:-2]
				type_map[name] = f'{base_type}_array'
			else:
				type_map[name] = dt
		elif isinstance(data_type, list) and len(data_type) > 1:
			# fallback: just use the first
			dt = data_type[0]
			if dt.endswith('[]'):
				base_type = dt[:-2]
				type_map[name] = f'{base_type}_array'
			else:
				type_map[name] = dt
		else:
			type_map[name] = str(data_type)
	return type_map

# Function to parse values based on their type
def parse_value_by_type(value, type_name):
	print(f"parse_value_by_type called")
	if type_name in ('text', 'string', 'uuid', 'geoCoordinates', 'phoneNumber', 'blob'):
		return str(value)
	elif type_name == 'boolean':
		if isinstance(value, bool):
			return value
		if isinstance(value, str):
			return value.lower() == 'true'
		return bool(value)
	elif type_name == 'int':
		try:
			return int(value)
		except Exception:
			return None
	elif type_name == 'number':
		try:
			return float(value)
		except Exception:
			return None
	elif type_name == 'date':
		# Accept both string and date/datetime
		if isinstance(value, (datetime, date)):
			return value.strftime('%Y-%m-%dT%H:%M:%S+00:00')
		elif isinstance(value, str):
			try:
				dt = datetime.fromisoformat(value)
				return dt.strftime('%Y-%m-%dT%H:%M:%S+00:00')
			except Exception:
				return value
		else:
			return str(value)
	elif type_name.endswith('_array'):
		base_type = type_name[:-6]
		if isinstance(value, list):
			return [parse_value_by_type(v, base_type) for v in value]
		try:
			arr = json.loads(value)
			return [parse_value_by_type(v, base_type) for v in arr]
		except Exception:
			return []
	elif type_name == 'object':
		if isinstance(value, dict):
			return value
		try:
			return json.loads(value)
		except Exception:
			return {}
	else:
		return value

# Function to format values for display
def format_value_for_display(value, type_name):
	print(f"format_value_for_display called")
	if type_name.endswith('_array') or type_name == 'object':
		return json.dumps(value, indent=2) if value else '[]' if type_name.endswith('_array') else '{}'
	elif type_name == 'date':
		if isinstance(value, str):
			try:
				return datetime.fromisoformat(value.replace('Z', '+00:00'))
			except Exception:
				return value
		elif isinstance(value, (datetime, date)):
			return value
		else:
			return value
	elif type_name == 'boolean':
		return bool(value)
	elif type_name == 'int':
		try:
			return int(value)
		except Exception:
			return 0
	elif type_name == 'number':
		try:
			return float(value)
		except Exception:
			return 0.0
	else:
		return str(value) if value is not None else ''

# Function to display the object as a table and edit its properties
def get_object_details():
	print(f"get_object_details called")
	collection_name = st.text_input("Collection Name")
	object_uuid = st.text_input("Object UUID")
	with_tenant = st.checkbox("Tenant", value=False)

	tenant_name = None
	if with_tenant:
		tenant_name = st.text_input("Tenant Name")

	col1, col2 = st.columns(2)
	with col1:
		fetch_object_clicked = st.button("Fetch The Object", use_container_width=True)
	with col2:
		check_node_clicked = st.button("Check the Object on the Nodes (APIs)", use_container_width=True)

	# Initialize session state for edit mode and object data
	if 'edit_mode' not in st.session_state:
		st.session_state.edit_mode = False
	if 'current_object' not in st.session_state:
		st.session_state.current_object = None
	if 'object_display' not in st.session_state:
		st.session_state.object_display = None
	if 'type_map' not in st.session_state:
		st.session_state.type_map = None

	# Fetch schema and build type map
	if collection_name and (st.session_state.type_map is None or st.session_state.get('last_collection_name') != collection_name):
		# Get API key and endpoint from session state
		active_endpoint = st.session_state.active_endpoint
		active_api_key = st.session_state.active_api_key
		if active_api_key and active_endpoint:
			schema = fetch_collection_config(active_endpoint, active_api_key, collection_name)
			if schema and 'error' not in schema:
				st.session_state.type_map = build_type_map_from_schema(schema)
				st.session_state.last_collection_name = collection_name
			else:
				st.session_state.type_map = None
				st.session_state.last_collection_name = None

	# "Fetch Object"
	if fetch_object_clicked:
		if not collection_name.strip() or not object_uuid.strip():
			st.error("Please insert both Collection Name and UUID.")
			return

		try:
			# Fetch and display object
			if with_tenant and tenant_name:
				data_object = get_object_in_tenant(st.session_state.client, collection_name, object_uuid, tenant_name)
			else:
				data_object = get_object_in_collection(st.session_state.client, collection_name, object_uuid)

			if data_object:
				st.session_state.current_object = data_object
				st.session_state.object_display = display_object_as_table(data_object)
				st.session_state.edit_mode = False
			else:
				st.error(f"Object with UUID '{object_uuid}' not found.")
		except ValueError:
			st.error("Invalid UUID: Not a valid UUID or unable to extract it.")
		except Exception as e:
			st.error(f"An error occurred: {e}")

	# Display object data if available
	if st.session_state.object_display is not None:
		st.markdown("### Object Data")
		st.dataframe(st.session_state.object_display, use_container_width=True)

		# Add Edit button below the table
		if not st.session_state.edit_mode:
			if st.button("Edit Object", type="primary"):
				st.session_state.edit_mode = True
				st.rerun()

	# Edit mode UI
	if st.session_state.edit_mode and st.session_state.current_object:
		st.markdown("### Edit Object Properties")

		# Create form for editing properties
		with st.form("edit_object_form"):
			edited_properties = {}
			type_map = st.session_state.type_map or {}
			# Display and edit each property
			for key, value in st.session_state.current_object.properties.items():
				type_name = type_map.get(key, 'text')
				st.markdown(f"#### {key} ({type_name})")
				if type_name.endswith('_array') or type_name == 'object':
					edited_properties[key] = st.text_area(
						"Value (JSON Array/Object)",
						value=format_value_for_display(value, type_name),
						height=100,
						key=f"textarea_{key}"
					)
				elif type_name == 'date':
					dt_val = format_value_for_display(value, type_name)
					if isinstance(dt_val, (datetime, date)):
						edited_properties[key] = st.date_input(
							"Value (Date)",
							value=dt_val,
							key=f"date_{key}"
						)
					else:
						edited_properties[key] = st.text_input(
							"Value (Date String)",
							value=str(dt_val),
							key=f"date_{key}"
						)
				elif type_name == 'number':
					try:
						num_val = float(value)
					except Exception:
						num_val = 0.0
					edited_properties[key] = st.number_input(
						"Value (Number)",
						value=num_val,
						key=f"number_{key}"
					)
				elif type_name == 'int':
					try:
						int_val = int(value)
					except Exception:
						int_val = 0
					edited_properties[key] = st.number_input(
						"Value (Int)",
						value=int_val,
						step=1,
						key=f"int_{key}"
					)
				elif type_name == 'boolean':
					bool_val = bool(value)
					if isinstance(value, str):
						bool_val = value.lower() == 'true'
					edited_properties[key] = st.checkbox(
						"Value (Boolean)",
						value=bool_val,
						key=f"bool_{key}"
					)
				else: # text and fallback
					edited_properties[key] = st.text_input(
						"Value (Text)",
						value=str(value),
						key=f"text_{key}"
					)
			col1, col2 = st.columns(2)
			with col1:
				submitted = st.form_submit_button("Save Changes", use_container_width=True)
			with col2:
				cancel = st.form_submit_button("Cancel", use_container_width=True)
			if submitted:
				try:
					# Parse the values before updating
					parsed_properties = {}
					for key, value in edited_properties.items():
						type_name = type_map.get(key, 'text')
						parsed_properties[key] = parse_value_by_type(value, type_name)
					# Update the object
					if with_tenant and tenant_name:
						update_object_properties(
							st.session_state.client,
							collection_name,
							object_uuid,
							parsed_properties,
							tenant_name
						)
					else:
						update_object_properties(
							st.session_state.client,
							collection_name,
							object_uuid,
							parsed_properties
						)
					st.success("Object updated successfully!")
					st.session_state.edit_mode = False
					# Refresh the object display
					if with_tenant and tenant_name:
						data_object = get_object_in_tenant(st.session_state.client, collection_name, object_uuid, tenant_name)
					else:
						data_object = get_object_in_collection(st.session_state.client, collection_name, object_uuid)
					st.session_state.current_object = data_object
					st.session_state.object_display = display_object_as_table(data_object)
					st.rerun()
				except Exception as e:
					st.error(f"Failed to update object: {e}")
			if cancel:
				st.session_state.edit_mode = False
				st.rerun()
	# "Check Object on a Node"
	if check_node_clicked:
		if not collection_name.strip() or not object_uuid.strip():
			st.error("Please insert both Collection Name and UUID.")
			return
		try:
			# Fetch node data and display table
			active_endpoint = st.session_state.active_endpoint
			active_api_key = st.session_state.active_api_key
			if with_tenant and tenant_name:
				data_object = find_object_in_tenant_on_nodes(active_endpoint, active_api_key, collection_name, object_uuid, tenant_name)
			else:
				data_object = find_object_in_collection_on_nodes(active_endpoint, active_api_key, collection_name, object_uuid)
			node_df = data_object
			st.dataframe(node_df, use_container_width=True)
			st.text("✔ Found | ✖ Not Found | N/A The node does not exist (Hardcoded 11 nodes as maximum for now)")
		except Exception as e:
			st.error(f"An error occurred while checking the object on nodes: {e}")

# Get collection configuration
def get_collection_configuration():
	print(f"get_collection_configuration called")
	st.markdown("### Collection Configuration")

	# Collection selection
	collections = list_collections(st.session_state.client)
	selected_collection = st.selectbox(
		"Select Collection",
		options=collections,
		help="Choose a collection to update its configuration"
	)

	if selected_collection:
		st.session_state.current_collection = selected_collection
		try:
			config = get_collection_config(st.session_state.client, selected_collection)
			if 'edit_collection_mode' not in st.session_state:
				st.session_state.edit_collection_mode = False
			if not st.session_state.edit_collection_mode:
				if st.button("Edit Collection", key="edit_collection_btn", use_container_width=True):
					st.session_state.edit_collection_mode = True
					st.rerun()
			else:
				update_collection_config_ui(config)
				if st.button("Cancel", key="cancel_edit_collection_btn", use_container_width=True):
					st.session_state.edit_collection_mode = False
					st.rerun()
		except Exception as e:
			st.error(f"Error in retrieving collection configuration. Reason: {str(e)}")

# Update collection configuration UI
def update_collection_config_ui(config):
	print(f"update_collection_config_ui called")
	# 1) Description + Inverted Index
	st.markdown("#### Description & Inverted Index Config")
	description = getattr(config, 'description', "")
	description = st.text_input("Description", value=description, key="desc_input")
	inverted = getattr(config, 'inverted_index_config', None)
	bm25_b = getattr(getattr(inverted, 'bm25', None), 'b', 0.75) if inverted else 0.75
	bm25_k1 = getattr(getattr(inverted, 'bm25', None), 'k1', 1.2) if inverted else 1.2
	cleanup_interval = getattr(inverted, 'cleanup_interval_seconds', 60) if inverted else 60
	stopwords = getattr(inverted, 'stopwords', None) if inverted else None
	stopwords_preset = getattr(stopwords, 'preset', StopwordsPreset.EN) if stopwords else StopwordsPreset.EN
	stopwords_add_list = getattr(stopwords, 'additions', []) if stopwords else []
	stopwords_remove_list = getattr(stopwords, 'removals', []) if stopwords else []
	stopwords_add = ", ".join(stopwords_add_list) if isinstance(stopwords_add_list, (list, tuple)) and stopwords_add_list else ""
	stopwords_remove = ", ".join(stopwords_remove_list) if isinstance(stopwords_remove_list, (list, tuple)) and stopwords_remove_list else ""
	bm25_b = st.number_input("BM25 b", value=float(bm25_b), min_value=0.0, max_value=1.0, step=0.01, key="bm25_b")
	bm25_k1 = st.number_input("BM25 k1", value=float(bm25_k1), min_value=0.0, step=0.01, key="bm25_k1")
	cleanup_interval = st.number_input("Cleanup Interval (s)", value=int(cleanup_interval), min_value=0, key="cleanup_interval")
	stopwords_preset_str = st.selectbox("Stopwords Preset", [e.name for e in StopwordsPreset], index=[e.name for e in StopwordsPreset].index(stopwords_preset.name if hasattr(stopwords_preset, 'name') else str(stopwords_preset)), key="stopwords_preset")
	stopwords_add = st.text_input("Stopwords Additions (comma separated)", value=stopwords_add, key="stop_add")
	stopwords_remove = st.text_input("Stopwords Removals (comma separated)", value=stopwords_remove, key="stop_remove")
	if st.button("Update Description & Inverted Index", use_container_width=True, key="save_desc_inv"):
		try:
			update_description_and_inverted_index(
				st.session_state.client,
				st.session_state.current_collection,
				description,
				bm25_b,
				bm25_k1,
				cleanup_interval,
				StopwordsPreset[stopwords_preset_str] if stopwords_preset_str else None,
				stopwords_add,
				stopwords_remove
			)
			st.success("Description & Inverted Index updated!")
		except Exception as e:
			st.error(f"Failed to update: {str(e)}")

	# 2) Multi-tenancy, Deletion Strategy & Replication
	st.markdown("#### Multi-tenancy, Deletion Strategy & Replication Config")
	multi = getattr(config, 'multi_tenancy_config', None)
	auto_tenant_creation = getattr(multi, 'auto_tenant_creation', False) if multi else False
	auto_tenant_activation = getattr(multi, 'auto_tenant_activation', False) if multi else False
	auto_tenant_creation = st.checkbox("Auto Tenant Creation", value=bool(auto_tenant_creation), key="auto_tenant_creation")
	auto_tenant_activation = st.checkbox("Auto Tenant Activation", value=bool(auto_tenant_activation), key="auto_tenant_activation")
	repl = getattr(config, 'replication_config', None)
	async_enabled = getattr(repl, 'async_enabled', False) if repl else False
	deletion_strategy = getattr(repl, 'deletion_strategy', None)
	allowed_deletion_strategies = ["DELETE_ON_CONFLICT", "NO_AUTOMATED_RESOLUTION", "TIME_BASED_RESOLUTION"]
	deletion_strategy_str = st.selectbox("Deletion Strategy", allowed_deletion_strategies, index=allowed_deletion_strategies.index(deletion_strategy.name if deletion_strategy else "DELETE_ON_CONFLICT"), key="del_strategy")
	async_enabled = st.checkbox("Async Enabled", value=bool(async_enabled), key="async_enabled")
	if st.button("Update Multi-tenancy & Replication", use_container_width=True, key="save_multi_repl"):
		try:
			update_multi_tenancy_and_replication(
				st.session_state.client,
				st.session_state.current_collection,
				auto_tenant_creation,
				auto_tenant_activation,
				async_enabled,
				deletion_strategy_str
			)
			st.success("Multi-tenancy & Replication updated!")
		except Exception as e:
			st.error(f"Failed to update: {str(e)}")

	# 3) HNSW Vector Index
	st.markdown("#### HNSW Vector Index Config")
	vector = getattr(config, 'vector_index_config', None)
	dynamic_ef_factor = getattr(vector, 'dynamic_ef_factor', 8) if vector else 8
	dynamic_ef_min = getattr(vector, 'dynamic_ef_min', 100) if vector else 100
	dynamic_ef_max = getattr(vector, 'dynamic_ef_max', 500) if vector else 500
	filter_strategy = getattr(vector, 'filter_strategy', None)
	flat_search_cutoff = getattr(vector, 'flat_search_cutoff', 10000) if vector else 10000
	vector_cache_max_objects = getattr(vector, 'vector_cache_max_objects', 1000000) if vector else 1000000
	dynamic_ef_factor = st.number_input("Dynamic EF Factor", value=int(dynamic_ef_factor), min_value=1, key="def")
	dynamic_ef_min = st.number_input("Dynamic EF Min", value=int(dynamic_ef_min), min_value=1, key="defmin")
	dynamic_ef_max = st.number_input("Dynamic EF Max", value=int(dynamic_ef_max), min_value=1, key="defmax")
	filter_strategy_str = st.selectbox("Filter Strategy", [e.name for e in VectorFilterStrategy], index=[e.name for e in VectorFilterStrategy].index(filter_strategy.name if filter_strategy else "SWEEPING"), key="filter_strategy")
	flat_search_cutoff = st.number_input("Flat Search Cutoff", value=int(flat_search_cutoff), min_value=0, key="fsc")
	vector_cache_max_objects = st.number_input("Vector Cache Max Objects", value=int(vector_cache_max_objects), min_value=0, key="vcmo")
	if st.button("Update HNSW Vector Index", use_container_width=True, key="save_hnsw"):
		try:
			update_hnsw_vector_index(
				st.session_state.client,
				st.session_state.current_collection,
				dynamic_ef_factor,
				dynamic_ef_min,
				dynamic_ef_max,
				filter_strategy_str,
				flat_search_cutoff,
				vector_cache_max_objects
			)
			st.success("HNSW Vector Index updated!")
		except Exception as e:
			st.error(f"Failed to update: {str(e)}")

	# 4) PQ Quantizer
	st.markdown("#### PQ Quantizer Config")
	quantizer = getattr(vector, 'quantizer', None) if vector else None
	pq_enabled = False
	pq_centroids = 256
	pq_segments = 8
	pq_training_limit = 10000
	pq_encoder_type = PQEncoderType.KMEANS
	pq_encoder_distribution = PQEncoderDistribution.NORMAL
	if quantizer is not None:
		pq_enabled = True
		pq_centroids = getattr(quantizer, 'centroids', 256)
		pq_segments = getattr(quantizer, 'segments', 8)
		pq_training_limit = getattr(quantizer, 'training_limit', 10000)
		encoder = getattr(quantizer, 'encoder', None)
		if encoder is not None:
			pq_encoder_type = getattr(encoder, 'type_', PQEncoderType.KMEANS)
			pq_encoder_distribution = getattr(encoder, 'distribution', PQEncoderDistribution.NORMAL)
	pq_enabled = st.checkbox("PQ Enabled", value=pq_enabled, key="pq_enabled")
	pq_centroids = st.number_input("PQ Centroids", value=int(pq_centroids), min_value=1, key="pq_centroids")
	pq_segments = st.number_input("PQ Segments", value=int(pq_segments), min_value=1, key="pq_segments")
	pq_training_limit = st.number_input("PQ Training Limit", value=int(pq_training_limit), min_value=1, key="pq_train")
	encoder_type_name = pq_encoder_type.name if hasattr(pq_encoder_type, 'name') else str(pq_encoder_type)
	encoder_distribution_name = pq_encoder_distribution.name if hasattr(pq_encoder_distribution, 'name') else str(pq_encoder_distribution)
	pq_encoder_type_str = st.selectbox("PQ Encoder Type", [e.name for e in PQEncoderType], index=[e.name for e in PQEncoderType].index(encoder_type_name), key="pq_enc_type")
	pq_encoder_distribution_str = st.selectbox("PQ Encoder Distribution", [e.name for e in PQEncoderDistribution], index=[e.name for e in PQEncoderDistribution].index(encoder_distribution_name), key="pq_enc_dist")
	if st.button("Update PQ Quantizer", use_container_width=True, key="save_pq"):
		try:
			update_pq_quantizer(
				st.session_state.client,
				st.session_state.current_collection,
				pq_enabled,
				pq_centroids,
				pq_segments,
				pq_training_limit,
				pq_encoder_type_str,
				pq_encoder_distribution_str
			)
			st.success("PQ Quantizer updated!")
		except Exception as e:
			st.error(f"Failed to update: {str(e)}")

def main():

	set_custom_page_config(page_title="Update")
	navigate()

	if st.session_state.get("client_ready"):

		update_side_bar_labels()

		# Create tabs for different update operations
		tab1, tab2 = st.tabs(["Update Object", "Update Collection Configuration"])
		with tab1:
			get_object_details()
		with tab2:
			get_collection_configuration()
	else:
		st.warning("Please Establish a connection to Weaviate in Cluster page!")

if __name__ == "__main__":
	main()
