# New Features for Squash Feature
We are going to add some new features to the squash feature. The idea is that the user will have the options to select squash strategies per column during the squash process. The user will still have the ability edit the squashed row, but the output row will be autopopulated based on the strategy selected for that column.

## Workflow
1. User selects the squash feature as they normally would.
2. User is asked if they want to create squash strategies for the different columns.
3. If the user selects no, the squash process continues as it normally would where it uses the majority value for each column to populate the squashed output row.
4. If the user selects yes, then they will be taken to a new screen where they are asked to select a squash strategy for each column. The deefault strategy should be majority, but the user can select from the following strategies:
    - Majority: The value that appears most frequently in the column will be used for the squashed output row.
    - First: The value from the first row in the group will be used for the squashed output row.
    - Last: The value from the last row in the group will be used for the squashed output row.
    - Concatenate: All values in the column will be concatenated together and separated by a delimiter (e.g. comma) to create the value for the squashed output row. The user will be able to provide a delimiter of their choice.
    - Remove: The column will be removed from the squashed output row.
5. Once the strategy is selected for each column, the user will have the option to have the selected strategy output to a different column name.
6. The squash report should begin by logging the selected squash strategies.
7. The squash process continues as it normally would, but the output row is populated based on the selected strategies for each column. The user still has the ability to edit the squashed output row before finalizing the squash process for each row, including adding new columns and other features that already exist.
