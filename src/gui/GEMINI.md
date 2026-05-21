# Project Specs - Pipeline GUI
 - Only modify files inside ./src/gui
 - Use dearpygui. 
 - The Pipeline should be made of modules, which are just nodes. 
   - Appearance: The modules should have their name on top with a gear all the way on the right of it, then under that header a dropdown where you can select a configuration. The modules should be on configuration 0 by default. The gear should open up a dialog box that allows you to change the config (found in the Module's class). The modules should have their inputs labeled on the left, and their output labeled on the right (the labels are the type returned, but removing the string "Transport" or "DataTransport" from the end if applicable). 
   - The outputs should be able to be dragged to other inputs provided the input types are the same, with an arrow pointing to the input. Each input can only be used once, outputs can be used multiple times. 
 - The modules should be able to be dragged in from a dock, preferably on the right, with the modules looking the exact same while in the dock as when not (only they can't be interacted with besides for dragging). 
 - You should be able to run the pipeline, with a dialog box (closable) showing up if there is an error.


# Chat rules
 - always run the program before stopping. Run using python -m src.gui.app
 - NEVER USE GIT COMMANDS