import dearpygui.dearpygui as dpg
from src.gui.module_manager import module_manager, Module

# Store references to created nodes to manage them
node_registry = {}
# Store links to check if an input is already used
active_links = {} # input_attr_id -> output_attr_id

def _add_module_to_editor_callback(sender, app_data, module_name):
    # module_to_add is an instance of the GUI's Module class
    # We need to get the original pipeline_module_class to create a new GUI Module instance
    original_gui_module = module_manager.get_module(module_name)
    if original_gui_module:
        new_gui_module_instance = Module(original_gui_module.pipeline_module.__class__)
        _create_dpg_node_from_module(new_gui_module_instance)

# Removed _handle_module_drop as drag and drop is not supported in this DPG version

def _show_error_dialog(message):
    if dpg.does_item_exist("error_dialog"):
        dpg.delete_item("error_dialog")
    with dpg.window(label="Error", modal=True, tag="error_dialog", autosize=True):
        dpg.add_text(message)
        dpg.add_button(label="Ok", callback=lambda s, a, u: dpg.delete_item("error_dialog"))

def _show_config_dialog(sender, app_data, user_data):
    module_name = user_data
    module = module_manager.get_module(module_name)

    if dpg.does_item_exist("config_dialog"):
        dpg.delete_item("config_dialog")

    with dpg.window(label=f"Configure {module.name}", modal=True, tag="config_dialog", autosize=True):
        dpg.add_text(f"Current Configuration: {module.get_current_config()}")
        dpg.add_combo(items=module.get_config_options(), default_value=module.get_current_config(), label="Select Config", tag=f"config_combo_{module_name}")
        dpg.add_button(label="Apply", callback=_apply_config_changes, user_data=module_name)
        dpg.add_button(label="Cancel", callback=lambda s, a, u: dpg.delete_item("config_dialog"))

def _apply_config_changes(sender, app_data, user_data):
    module_name = user_data
    module = module_manager.get_module(module_name)
    selected_config = dpg.get_value(f"config_combo_{module_name}")
    
    # Store the old node_id and position
    old_node_id = module.node_id
    old_node_pos = dpg.get_item_pos(old_node_id) if dpg.does_item_exist(old_node_id) else [0, 0]

    # Update the module's configuration
    module.set_current_config(selected_config)
    print(f"Applied config '{selected_config}' to module '{module_name}'")

    # Delete the old node and its links
    if dpg.does_item_exist(old_node_id):
        # Get all links connected to this node
        node_links = dpg.get_node_links(old_node_id)
        for link_id in node_links:
            delink_callback(None, link_id) # Use delink_callback to properly remove from active_links
        dpg.delete_item(old_node_id)
        del node_registry[old_node_id]

    # Create a new node with the updated module information
    new_node_id = _create_dpg_node_from_module(module)
    dpg.set_item_pos(new_node_id, old_node_pos)

    dpg.delete_item("config_dialog")

def _create_dpg_node_from_module(module: Module):
    """
    Creates a DPG node representing a module in the node editor.
    """
    with dpg.node(label=module.name, parent="node_editor") as node_id:
        module.node_id = node_id
        node_registry[node_id] = module

        # Header with module name and gear icon
        with dpg.node_attribute(attribute_type=dpg.mvNode_Attr_Static):
            with dpg.group(horizontal=True):
                dpg.add_text(module.name)
                dpg.add_spacer(width=50) # Placeholder for spacing
                dpg.add_button(label="⚙", callback=_show_config_dialog, user_data=module.name) # Gear icon

        # Configuration dropdown
        with dpg.node_attribute(attribute_type=dpg.mvNode_Attr_Static):
            dpg.add_combo(items=module.get_config_options(), default_value=module.get_current_config(), label="Config", enabled=False) # Display only, config changed via gear

        # Inputs
        for i, (input_name, input_type) in enumerate(module.inputs):
            with dpg.node_attribute(attribute_type=dpg.mvNode_Attr_Input) as attr_id:
                dpg.add_text(module.get_inputs_for_display()[i])
                module.input_attr_ids[attr_id] = (input_type, input_name)

        # Outputs
        for i, (output_name, output_type) in enumerate(module.outputs):
            with dpg.node_attribute(attribute_type=dpg.mvNode_Attr_Output) as attr_id:
                dpg.add_text(module.get_outputs_for_display()[i])
                module.output_attr_ids[attr_id] = (output_type, output_name)
    return node_id

def link_callback(sender, app_data):
    """
    Callback for creating links between nodes.
    app_data[0] is the output attribute, app_data[1] is the input attribute
    """
    link_output_attr = app_data[0]
    link_input_attr = app_data[1]

    # Check if input is already linked
    if link_input_attr in active_links:
        _show_error_dialog("This input is already connected to an output.")
        return

    # Get parent nodes
    output_node = dpg.get_item_parent(link_output_attr)
    input_node = dpg.get_item_parent(link_input_attr)

    # Get module objects
    output_module = node_registry.get(output_node)
    input_module = node_registry.get(input_node)

    if not output_module or not input_module:
        _show_error_dialog("Could not find modules for the selected attributes.")
        return

    # Get types
    output_type, _ = output_module.output_attr_ids.get(link_output_attr)
    input_type, _ = input_module.input_attr_ids.get(link_input_attr)

    if output_type is None or input_type is None:
        _show_error_dialog("Could not determine types for the selected attributes.")
        return

    # Type checking
    if output_type != input_type:
        _show_error_dialog(f"Type mismatch: Output is '{output_type}', Input is '{input_type}'.")
        return

    # Create link
    dpg.add_node_link(link_output_attr, link_input_attr, parent=sender)
    active_links[link_input_attr] = link_output_attr # Store the link

def delink_callback(sender, app_data):
    """
    Callback for deleting links between nodes.
    app_data is the link ID
    """
    # Remove from active_links
    link_id = app_data
    link_input_attr = dpg.get_item_link_attribute(link_id)[1] # Get input attribute from link
    if link_input_attr in active_links:
        del active_links[link_input_attr]
    dpg.delete_item(link_id)

def run_pipeline(sender, app_data):
    print("Running pipeline...")
    # 1. Build Graph
    graph = {node_id: [] for node_id in node_registry.keys()} # Adjacency list: node -> [connected_nodes]
    in_degree = {node_id: 0 for node_id in node_registry.keys()}
    output_data_store = {} # Stores outputs from executed modules

    # Map attribute IDs to their parent node IDs
    attr_to_node = {}
    for node_id, module in node_registry.items():
        for attr_id in module.input_attr_ids:
            attr_to_node[attr_id] = node_id
        for attr_id in module.output_attr_ids:
            attr_to_node[attr_id] = node_id

    for input_attr, output_attr in active_links.items():
        source_node = attr_to_node.get(output_attr)
        target_node = attr_to_node.get(input_attr)

        if source_node and target_node:
            graph[source_node].append((target_node, output_attr, input_attr))
            in_degree[target_node] += 1
        else:
            _show_error_dialog("Invalid link detected in pipeline graph.")
            return

    # 2. Topological Sort (Kahn's Algorithm)
    queue = [node_id for node_id, degree in in_degree.items() if degree == 0]
    sorted_nodes = []

    while queue:
        current_node_id = queue.pop(0)
        sorted_nodes.append(current_node_id)

        for neighbor_node_id, _, _ in graph[current_node_id]:
            in_degree[neighbor_node_id] -= 1
            if in_degree[neighbor_node_id] == 0:
                queue.append(neighbor_node_id)

    if len(sorted_nodes) != len(node_registry):
        _show_error_dialog("Circular dependency detected in the pipeline!")
        return

    # 3. Execute Modules
    for node_id in sorted_nodes:
        module = node_registry[node_id]
        module_inputs = {}

        # Gather inputs for the current module
        for input_attr_id, (input_type, input_name) in module.input_attr_ids.items():
            # Find which output is connected to this input
            connected_output_attr_id = None
            for active_input_attr, active_output_attr in active_links.items():
                if active_input_attr == input_attr_id:
                    connected_output_attr_id = active_output_attr
                    break

            if connected_output_attr_id:
                # Find the module that produced this output
                source_node_id = attr_to_node[connected_output_attr_id]
                source_module = node_registry[source_node_id]
                # Get the output name from the source module's output_attr_ids
                _, output_name = source_module.output_attr_ids.get(connected_output_attr_id)
                
                if output_name:
                    module_inputs[input_name] = output_data_store.get((source_node_id, output_name))
                else:
                    _show_error_dialog(f"Could not find output name for connected attribute {connected_output_attr_id}")
                    return
            elif module.inputs: # If module has inputs but this one is not connected
                _show_error_dialog(f"Module '{module.name}' has unconnected input '{input_name}' of type '{input_type}'.")
                return

        try:
            outputs = module.execute(module_inputs)
            for output_name, output_value in outputs.items():
                output_data_store[(node_id, output_name)] = output_value
        except Exception as e:
            _show_error_dialog(f"Error executing module '{module.name}': {e}")
            return

    print("Pipeline executed successfully!")
    _show_error_dialog("Pipeline executed successfully!") # Use error dialog as success dialog for now

def _resize_callback(sender, app_data):
    viewport_width = dpg.get_viewport_width()
    viewport_height = dpg.get_viewport_height()

    module_dock_width = 200
    pipeline_area_width = viewport_width - module_dock_width
    
    dpg.set_item_width("ModuleDock", module_dock_width)
    dpg.set_item_height("ModuleDock", viewport_height)
    dpg.set_item_pos("ModuleDock", [viewport_width - module_dock_width, 0])

    dpg.set_item_width("PipelineArea", pipeline_area_width)
    dpg.set_item_height("PipelineArea", viewport_height)
    dpg.set_item_pos("PipelineArea", [0, 0])

# Global variable to store the last mouse position for panning
last_mouse_pos = None

def _node_editor_mouse_drag_handler(sender, app_data):
    global last_mouse_pos
    # Check if the mouse is being dragged within the node_editor bounds
    node_editor_pos = dpg.get_item_pos("node_editor")
    node_editor_size = dpg.get_item_rect_size("node_editor")
    mouse_pos_viewport = dpg.get_mouse_pos(local=False)

    if (node_editor_pos[0] <= mouse_pos_viewport[0] <= node_editor_pos[0] + node_editor_size[0] and
        node_editor_pos[1] <= mouse_pos_viewport[1] <= node_editor_pos[1] + node_editor_size[1]):

        if dpg.is_mouse_button_down(dpg.mvMouseButton_Middle): # Middle mouse button for panning
            current_mouse_pos = mouse_pos_viewport
            if last_mouse_pos is not None:
                delta_x = current_mouse_pos[0] - last_mouse_pos[0]
                delta_y = current_mouse_pos[1] - last_mouse_pos[1]
                
                # Get current pan position
                current_pan = dpg.get_node_editor_panning("node_editor")
                
                # Apply delta to pan position
                dpg.set_node_editor_panning("node_editor", [current_pan[0] + delta_x, current_pan[1] + delta_y])
            last_mouse_pos = current_mouse_pos
        else:
            last_mouse_pos = None
    else:
        last_mouse_pos = None

def _node_editor_mouse_release_handler(sender, app_data):
    global last_mouse_pos
    last_mouse_pos = None

def main():
    dpg.create_context()
    dpg.create_viewport(title='Pipeline GUI', width=1200, height=800)
    dpg.setup_dearpygui()

    # Define windows with initial placeholder sizes/positions
    with dpg.window(label="Pipeline Editor", tag="PipelineWindow", no_title_bar=True, no_resize=False, no_move=True, no_collapse=True, no_close=True, no_background=False):
        with dpg.menu_bar():
            dpg.add_button(label="Run Pipeline", callback=run_pipeline)

    with dpg.window(label="Modules", tag="ModuleDock", no_close=True, no_collapse=False, no_move=True):
        dpg.add_text("Available Modules")
        for module_name in module_manager.get_module_names():
            dpg.add_button(label=module_name, width=-1, callback=_add_module_to_editor_callback, user_data=module_name)

    with dpg.window(label="Pipeline", tag="PipelineArea", no_close=True, no_scrollbar=True):
        with dpg.node_editor(callback=link_callback, delink_callback=delink_callback, tag="node_editor", width=-1, height=-1):
            pass
    
    # Create handler registry as a top-level item
    with dpg.handler_registry(tag="node_editor_handlers"):
        dpg.add_mouse_drag_handler(button=dpg.mvMouseButton_Middle, callback=_node_editor_mouse_drag_handler)
        dpg.add_mouse_release_handler(button=dpg.mvMouseButton_Middle, callback=_node_editor_mouse_release_handler)
    
    # Call resize callback once to set initial sizes and positions
    _resize_callback(None, None)

    dpg.show_viewport()
    dpg.set_primary_window("PipelineWindow", True)
    dpg.set_viewport_resize_callback(_resize_callback)
    dpg.start_dearpygui()
    dpg.destroy_context()

if __name__ == "__main__":
    main()

