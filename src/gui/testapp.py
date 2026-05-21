import dearpygui.dearpygui as dpg

dpg.create_context()

def link_callback(sender, app_data):
    dpg.add_node_link(app_data[0], app_data[1], parent=sender)

with dpg.window(label="Node Editor"):
    with dpg.node_editor(callback=link_callback):
        with dpg.node(label="Node 1"):
            with dpg.node_attribute(attribute_type=dpg.mvNode_Attr_Output):
                dpg.add_text("Output")

        with dpg.node(label="Node 2"):
            with dpg.node_attribute(attribute_type=dpg.mvNode_Attr_Input):
                dpg.add_text("Input")

dpg.create_viewport(title="Flow Editor")
dpg.setup_dearpygui()
dpg.show_viewport()
dpg.start_dearpygui()
dpg.destroy_context()