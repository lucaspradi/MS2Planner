# MS2Planner: Scientific and Technical Explanation

MS2Planner is a tool designed for planning targeted mass spectrometry (MS2) acquisition experiments. It optimizes the data collection process in liquid chromatography-mass spectrometry (LC-MS) by determining the most efficient paths for data acquisition.

## Scientific Background

In mass spectrometry-based metabolomics and proteomics, samples are analyzed using techniques like liquid chromatography coupled with mass spectrometry (LC-MS). During analysis:

1. Compounds are separated by liquid chromatography based on their chemical properties
2. Compounds elute at different retention times (RT)
3. Mass spectrometry detects the mass-to-charge ratio (m/z) of ionized compounds
4. MS2 (tandem mass spectrometry) involves fragmenting selected ions for detailed structural information

The challenge is that instruments can't perform MS2 on all ions simultaneously, so intelligent selection strategies are needed to maximize useful information collection.

## Core Functionality

MS2Planner addresses this challenge by providing three different modes for planning MS2 acquisition:

### 1. Apex Mode
This mode identifies feature apexes (points of maximum intensity during elution) and applies a path-finding algorithm to optimize data collection. It prioritizes:
- High-intensity features
- Features with significant difference between sample and blank
- Efficient transitions between features to maximize data collection

### 2. Baseline Mode
This is a simpler approach that:
- Divides the RT dimension into fixed-width windows (specified by `-win_len`)
- Within each window, selects the top N (`num_path`) highest intensity ions
- Does not optimize transitions between features

### 3. Curve Mode
The most sophisticated mode that:
- Uses both apex information and raw MS1 data
- Applies path-finding on the actual elution profiles (curves) of the compounds
- Can cluster similar features to optimize collection
- Takes into account restrictions in RT and m/z space

## Data Processing Workflow

1. **Input Processing**:
   - Reads feature tables containing m/z, RT, charge, blank intensity, and sample intensity
   - For curve mode, also reads raw MS1 data (.mzML or .mzTab)

2. **Feature Filtering**:
   - Removes features below intensity threshold (`intensity_threshold`)
   - Removes features with insufficient sample-to-blank ratio (`intensity_ratio`)
   - Limits features with the same RT to the most intense ones (`max_same_RT`)

3. **Path Generation**:
   - **Apex/Curve**: Uses graph-based algorithms to find optimal paths through feature space
   - **Baseline**: Uses simple window-based selection

4. **Output Generation**:
   - Creates paths in text format
   - Each path contains feature information: m/z center, isolation window, duration, RT range, intensity, apex RT, and charge

## Mathematical Concepts

1. **Path Finding Algorithm** (Apex and Curve modes):
   - Creates a graph where nodes are features and edges represent transitions
   - Edge weights incorporate intensity, distance (in RT), and other factors
   - Uses modified shortest path algorithms to maximize collected information

2. **Intensity Accumulation** (`intensity_accu`):
   - Handles the trade-off between dwelling on a single intense feature vs. collecting data from multiple features
   - Represents the amount of intensity to collect from a single feature

3. **Restriction Area** (Curve mode):
   - Defines the L1 norm (Manhattan distance) in RT-m/z space
   - Features outside this area are excluded from consideration

## Apex Mode Implementation Details

The Apex Mode is implemented in `path_apex.py` and follows this technical workflow:

1. **Data Reading and Feature Filtering**:
   - Loads feature data from input files containing m/z, RT, charge, blank intensity, and sample intensity
   - Features with zero intensity or below threshold intensity are removed
   - Features with sample-to-blank ratio below specified threshold are filtered out
   - When multiple features share the exact same retention time, only the top N most intense ones (specified by `max_same_RT`) are retained

2. **Graph Construction**:
   - Each feature is represented by two nodes: a left node (beginning of acquisition) and a right node (end of acquisition)
   - The acquisition time for each feature is calculated based on feature intensity and `intensity_accu` parameter:
     ```
     rt_isolation = intensity_accu / feature_intensity
     rt_isolation = min(max_time, max(rt_isolation, min_time))
     ```
   - The left node is positioned at `RT - 0.5 * rt_isolation`
   - The right node is positioned at `RT + 0.5 * rt_isolation + delay`
   - An edge connects the left and right nodes with a negative weight equal to the feature's intensity (negative because the algorithm maximizes absolute value)

3. **Path Finding Algorithm**:
   - A directed acyclic graph (DAG) is created with two additional nodes: a source (0) and a sink (num_node+1)
   - Edges connect nodes in chronological order of their RT values
   - A modified topological sort-based shortest path algorithm finds the path with the maximum intensity sum
   - This algorithm ensures the path follows the chronological order of retention times

4. **Iterative Path Generation**:
   - For each of the `num_path` paths:
     - Construct the graph
     - Find the shortest path
     - Extract the path (sequence of features)
     - Remove visited features from the dataset
     - Repeat with remaining features for subsequent paths

5. **Output Generation**:
   - For each path, detailed information is recorded:
     - Mass/charge (m/z) values
     - Isolation window width
     - Acquisition duration
     - Start and end retention times
     - Feature intensity
     - Apex retention time
     - Charge state
     - Feature ID (when available)
   - Results are saved as CSV files for instrument method creation

This implementation effectively balances the need to acquire data from high-intensity features while optimizing the time spent on each feature and minimizing dead time between acquisitions.

## Baseline Mode Implementation Details

The Baseline Mode is implemented in `path_baseline.py` and follows a simpler, more straightforward approach:

1. **Data Reading and Feature Filtering**:
   - Like in Apex Mode, feature data is loaded from input files containing m/z, RT, charge, blank intensity, and sample intensity
   - Similar filtering is applied: removing features with zero intensity, below threshold intensity, or insufficient sample-to-blank ratio
   - Features with the same RT are limited to the top N most intense ones (specified by `max_same_RT`)

2. **Window-based Feature Selection**:
   - Instead of using a graph-based approach, Baseline Mode divides the chromatogram into fixed-width time windows
   - The window length is specified by the `window_len` parameter (plus `delay` time)
   - For each time window:
     ```
     window_start = current_position
     window_end = window_start + window_len
     ```

3. **Feature Prioritization Within Windows**:
   - Within each time window, features are sorted by intensity in descending order
   - The top N features (specified by `num_path`) with the highest intensities are selected
   - This creates up to `num_path` parallel acquisition paths across the entire RT range
   - Each feature in a path is assigned the full window duration for acquisition

4. **Sequential Window Processing**:
   - The algorithm processes windows sequentially from the earliest RT to the latest
   - Once a window is processed, the next window starts at the end of the current window
   - This ensures complete coverage of the RT range without overlaps or gaps

5. **Output Generation**:
   - Similar to Apex Mode, detailed information for each selected feature is recorded:
     - Mass/charge (m/z) values
     - Isolation window width
     - Duration (equal to window length)
     - Start and end retention times
     - Feature intensity
     - Apex retention time
     - Charge state
     - Feature ID (when available)
   - Results are saved as CSV files for each path

The Baseline Mode implementation is computationally simpler than Apex Mode, as it doesn't require graph construction or shortest path algorithms. This makes it faster to execute and easier to understand. However, it sacrifices some optimization potential by not considering the optimal transition between features within or across windows. The approach is well-suited for instruments with fixed cycle times or when a straightforward acquisition strategy is preferred.

## Curve Mode Implementation Details

The Curve Mode is implemented in `path_curve.py` and represents the most sophisticated approach in MS2Planner. It processes raw MS1 data alongside feature tables to create paths that follow actual elution profiles (curves):

1. **Data Integration from Multiple Sources**:
   - Loads feature data from input files (containing m/z, RT, charge, blank intensity, sample intensity)
   - Also loads raw MS1 data from mzML or mzTab files with actual scan intensities
   - Matches MS1 raw data points with feature apex information

2. **Clustering Features with Raw MS1 Data**:
   - Implements two clustering algorithms to group related signals:
     - **k-Nearest Neighbors (kNN)**: Groups data points based on retention time and m/z proximity
     - **Gaussian Mixture Model (GMM)**: Uses probabilistic models to cluster data points
   - Each algorithm has specific parameters:
     ```
     # For kNN clustering
     labels = kNNCluster(data, centroid_dic, restriction)
     labels_clustered = kNN(data, labels, centroid_dic, restriction)
     
     # For GMM clustering
     labels = GMMCluster(data, centroid_dic, restriction, True)
     data_clean = data[labels != -1]
     labels_clustered = GMM(data_clean[:, :2], centers, centroid_dic, n_iter, Var_init, Var_max)
     ```
   - The restriction parameter defines a 2D window in RT-m/z space for feature inclusion

3. **Node and Cluster Creation**:
   - Creates nodes representing data points with the same retention time in a cluster
   - Each node tracks:
     - Retention time
     - m/z range (minimum and maximum m/z values)
     - Total intensity of all points in the node
     - Cluster membership
   - Nodes are then grouped into clusters based on their MS2 feature assignment
   - Clusters store the total intensity and all member nodes

4. **Complex Graph Construction**:
   - Creates a directed acyclic graph (DAG) with:
     - Nodes representing individual scan points
     - Edges connecting nodes in retention time order
     - Edge weights based on feature intensity
   - Implements a topological sort-based shortest path algorithm
   - Two types of edges are created:
     - Weight -1 edges: Connect nodes within the same cluster (collecting data from a feature)
     - Weight 0 edges: Connect nodes between different clusters (transitions between features)

5. **Path Finding with Accumulation Constraints**:
   - Defines an `intensity_accu` parameter that controls how much intensity to collect from a single feature
   - Adds dwell time constraints through the `min_scan` and `max_scan` parameters
   - Finds paths that maximize total collected intensity while respecting constraints
   - Handles the trade-off between dwelling on intense features vs. collecting more diverse data

6. **Multi-dimensional Optimization**:
   - Respects the actual elution profile shape through the raw MS1 data
   - Considers both m/z and RT dimensions simultaneously
   - Allows for isolation window adjustment based on observed peak width
   - Optimizes across multiple variables: intensity, retention time, and m/z isolation

7. **Iterative Path Generation with Memory Management**:
   - Generates multiple acquisition paths by:
     - Building the graph for remaining features
     - Finding the optimal path
     - Removing collected features
     - Repeating for subsequent paths
   - Implements memory management strategies (garbage collection) to handle large datasets
   - Provides detailed logging of path generation progress

8. **Output Generation**:
   - For each path, records comprehensive information:
     - Mass/charge (m/z) values (dynamic, based on observed peak width)
     - Isolation window width (adaptive, based on observed m/z range)
     - Start and end retention times (based on actual elution profile)
     - Feature intensity
     - Apex retention time
     - Charge state
     - Feature ID (when available)
   - Results are saved as CSV files for instrument method creation

The Curve Mode implementation represents the most powerful approach in MS2Planner, effectively capturing the true chromatographic behavior of features. It's particularly valuable for complex samples where feature overlap and co-elution are common. The approach significantly increases the information content of acquired MS2 data by optimizing acquisition based on the actual shape of elution profiles rather than just apex information.

## Command-Line Interface and Integration

MS2Planner's three acquisition modes are unified through the `path_finder.py` script, which serves as the main command-line interface for the tool:

1. **Command-Line Argument Parsing**:
   - Uses Python's `argparse` library to provide a comprehensive user interface
   - Implements extensive validation of parameters for each mode
   - Offers helpful warnings when inappropriate parameters are provided for a particular mode:
     ```python
     if mode == "apex":
         # Validate that apex-specific parameters are provided
         # Warn if baseline or curve mode parameters are provided
         if window_len is not None:
             logger.warning("win_len should not be input for apex mode")
     ```

2. **Common Required Parameters**:
   - `mode`: Specifies which algorithm to use (baseline, apex, or curve)
   - `input_filename`: Path to the feature table from which to read data
   - `outfile_name`: Path where to save the generated acquisition paths
   - `intensity`: Intensity threshold for feature filtering
   - `intensity_ratio`: Sample-to-blank ratio threshold for feature filtering
   - `num_path`: Number of acquisition paths to generate

3. **Mode-Specific Optional Parameters**:
   - **Baseline Mode**:
     - `-win_len`: Window length for dividing the RT dimension
     - `-isolation`: Mass isolation window width in m/z
     - `-delay`: Delay time between acquisitions
   
   - **Apex Mode**:
     - `-intensity_accu`: Target accumulated intensity per feature
     - `-isolation`: Mass isolation window width in m/z
     - `-delay`: Delay time between feature acquisitions
     - `-min_scan` and `-max_scan`: Lower and upper bounds on scan period
   
   - **Curve Mode**:
     - `-infile_raw`: Path to raw MS1 data file (.mzML or .mzTab)
     - `-intensity_accu`: Target accumulated intensity per feature
     - `-restriction`: Two-dimensional RT and m/z window for clustering
     - `-isolation`: Mass isolation window width in m/z
     - `-delay`: Delay time between feature acquisitions
     - `-min_scan` and `-max_scan`: Lower and upper bounds on scan period
     - `-cluster`: Clustering algorithm to use (kNN or GMM)

4. **Parameter Pre-processing**:
   - Some parameters undergo transformations before being passed to the respective modules
   - For example, intensity accumulation is scaled logarithmically:
     ```python
     # Scale intensity_accu for apex and curve modes
     intensity_accu = np.exp(np.log(intensity_accu) + 2.5)
     ```

5. **Mode Workflow Orchestration**:
   - The script implements three separate workflow branches for each mode
   - For all modes, the general workflow is:
     1. Load and validate parameters specific to the mode
     2. Read input feature data
     3. Filter features based on intensity and intensity ratio
     4. Generate acquisition paths
     5. Write results to output files
   - Progress is tracked through comprehensive logging:
     ```python
     logger.info("=============")
     logger.info("Begin Finding Path")
     logger.info("=============")
     ```

6. **Error Handling**:
   - Implements robust error handling with detailed logging
   - Try-except blocks around critical operations ensure graceful failure
   - If errors occur, descriptive messages are logged to help diagnose the problem:
     ```python
     except:
         logger.error("error in generating path", exc_info=sys.exc_info())
         sys.exit()
     ```

7. **Output Format Selection**:
   - Provides two output formats:
     - Standard format with separate files for each path
     - Combined format when using MZmine 3 feature tables (with sample and background names)
   - The output format is selected automatically based on input parameters:
     ```python
     if sample_name is None and bg_name is None:
         apex.WriteFile(outfile, paths_rt, paths_mz, paths_charge,
                       edge_intensity_dic, isolation, delay, min_scan, max_scan)
     else:
         apex.WriteFileFormatted(outfile, paths_rt, paths_mz, paths_charge,
                                edge_intensity_dic, isolation, delay, min_scan, max_scan, rt_mz_feature)
     ```

This unified command-line interface makes MS2Planner accessible and user-friendly while providing advanced parameter customization for each acquisition mode. The integration of the three modes through this common interface enables users to easily switch between different strategies without changing their workflow or data formats.

## Parameters and Constraints

Several parameters control the behavior:
- `intensity_threshold` and `intensity_ratio`: Control feature filtering
- `isolation`: Mass isolation window width (Da)
- `delay`: Minimum time required to switch between features
- `min_scan` and `max_scan`: Bounds on scan period
- `restriction`: Limits the RT and m/z space for curve mode
- `cluster`: Clustering algorithm for curve mode (kNN or GMM)

## Applications and Use Cases

MS2Planner is particularly useful for:
1. Targeted metabolomics where specific compounds need to be analyzed
2. Discovery metabolomics where optimal coverage of the metabolome is desired
3. Limited-sample scenarios where efficient data collection is critical
4. Instruments with limited scanning capabilities that need optimization

This detailed scientific explanation covers how MS2Planner processes data, its algorithms, and its applications in mass spectrometry-based research. The tool effectively bridges analytical chemistry, computer science, and bioinformatics to optimize data acquisition strategies in mass spectrometry.

## System Architecture and File Interactions

MS2Planner is structured as a modular system with clear separation of concerns across multiple Python files:

1. **Integration and User Interface (`path_finder.py`)**:
   - Serves as the main entry point and command-line interface
   - Imports and coordinates the three mode-specific modules:
     ```python
     import path_apex as apex
     import path_baseline as baseline
     import path_curve as curve
     ```
   - Parses command-line arguments and directs execution to the appropriate module
   - Implements separate workflow branches for each acquisition mode
   - Handles error conditions and logging across all modules

2. **Apex Mode Implementation (`path_apex.py`)**:
   - Contains all functionality specific to the Apex Mode
   - Provides functions for:
     - Reading and filtering feature data
     - Constructing directed acyclic graphs for path finding
     - Implementing topological sort-based shortest path algorithms
     - Generating paths that maximize intensity collection
     - Writing output files in both standard and formatted modes
   - Called by `path_finder.py` when the user selects "apex" mode

3. **Baseline Mode Implementation (`path_baseline.py`)**:
   - Contains all functionality specific to the simpler Baseline Mode
   - Provides functions for:
     - Reading and filtering feature data
     - Dividing the retention time range into fixed-width windows
     - Selecting the most intense features within each window
     - Creating multiple parallel acquisition paths
     - Writing output files in both standard and formatted modes
   - Called by `path_finder.py` when the user selects "baseline" mode

4. **Curve Mode Implementation (`path_curve.py`)**:
   - Contains all functionality specific to the advanced Curve Mode
   - Provides functions for:
     - Reading feature data and raw MS1 data
     - Implementing kNN and GMM clustering algorithms
     - Creating nodes and clusters from raw data points
     - Building complex graphs with intensity-weighted edges
     - Implementing memory-efficient path finding algorithms
     - Writing detailed output files
   - Called by `path_finder.py` when the user selects "curve" mode

5. **Data Flow and Processing Pipelines**:
   - All three implementation files share a similar workflow structure:
     1. Data reading (`ReadFile` functions)
     2. Feature filtering (`DataFilter` functions)
     3. Path generation (`PathGen` functions)
     4. Output writing (`WriteFile` functions)
   - This consistent structure allows `path_finder.py` to interact with each module in a uniform way
   - Data formats are standardized across modules to enable seamless integration

6. **Common Algorithmic Patterns**:
   - Both Apex and Curve modes use similar graph-based algorithms:
     - The `Graph` class appears in both `path_apex.py` and `path_curve.py`
     - Both implement topological sort-based shortest path algorithms
     - Both use negative weights to maximize collected intensity
   - Feature filtering logic is similar across all three modules:
     - Removing features with intensity below threshold
     - Filtering based on sample-to-blank intensity ratio
     - Limiting features with the same RT to the top N most intense

7. **External Dependencies**:
   - Core scientific computing libraries:
     - NumPy for numerical operations
     - Pandas for data manipulation
     - SciPy for statistical algorithms (GMM implementation)
   - Mass spectrometry-specific libraries:
     - pymzml for reading MS1 data in mzML format

This modular architecture allows MS2Planner to:
- Maintain clean separation between different acquisition strategies
- Share common code patterns and algorithms where appropriate
- Provide a unified interface to users via the command-line tool
- Enable future extension with new acquisition modes or algorithms

The system effectively balances flexibility and reusability while providing specialized implementations for each acquisition strategy, all unified through a common command-line interface in `path_finder.py`.