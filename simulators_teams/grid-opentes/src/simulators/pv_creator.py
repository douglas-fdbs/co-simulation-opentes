# --- Library Imports ---
import pandas as pd              # Data manipulation and CSV file handling
import py_dss_interface          # Python interface for OpenDSS (EPRI)
from pathlib import Path         # Object-oriented filesystem paths
from math import ceil            # Ceiling function to calculate total simulation points
from random import choice, seed  # Random node selection and reproducibility seeding

# --- Environment and Path Configurations ---
BASE_DIR = Path(".").resolve()
INFO_PV_FILE = BASE_DIR/'src'/'data'/'InfoPV'/'power_station_metadata.csv'
SOLAR_STATION_FILES = BASE_DIR/'src'/'data'/'InfoPV'/'solar_station'
SCRIPT_DSS = BASE_DIR/'src'/'data'/'13Bus'/'IEEE13Nodeckt.dss'
OUTPUT_DIR = BASE_DIR/'src'/'data'/'13Bus'
OUTPUT_IRRAD_CSV = OUTPUT_DIR/'ieee13_shape_pv_5min.csv'
OUTPUT_TEMP_CSV = OUTPUT_DIR/'ieee13_temperature_5min.csv'
OUTPUT_DSS_FILE = OUTPUT_DIR/'ieee13_pv.dss'

PV_list = pd.read_csv(INFO_PV_FILE)

# --- Simulation Control Variables ---
t_simulation = 24*60*1              # Total simulation time in minutes
npts_origin = ceil(t_simulation/15) # Original data points (15-min base)
step = '5min'                       # Target simulation time step (e.g., '5s', '5min', '2h')
start_date = "2026-01-01 00:00:00"  # Target simulation start timestamp for the final outputs 
my_seed = 25                        # Seed for reproducibility of random bus sampling

def PVCreator(QtdPVs,
              SCRIPT_DSS = SCRIPT_DSS,
              PV_list = PV_list,
              step = step,
              PV_dictionaries_list = None,
              my_seed = my_seed,
              bus_multi_PV: bool = False,
              npts_origin:int = npts_origin,
              ignore_buses: list = None):
    """
    Automates bus selection and creation of Photovoltaic (PV) systems in an OpenDSS circuit.

    The function identifies compatible buses, randomly selects connection points, 
    and instantiates PVGenerator objects for data curve processing.

    Args:
        QtdPVs (int): Number of PV systems to be randomly installed.
        SCRIPT_DSS (str/Path, optional): Path to the .dss circuit script.
        PV_list (pd.DataFrame, optional): PV plant metadata (BR-PVGen dataset).
        step (str, optional): Time step for linear interpolation (e.g., '5min').
        PV_dictionaries_list (list, optional): Base list for PV configuration dictionaries.
        my_seed (int, optional): Seed for reproducible random bus sampling.
        npts_origin (int, optional): Number of points in the original time series.
        bus_multi_pv (bool, optional): Controls bus reuse during the random sampling process. When False, already occupied or manually defined buses are filtered out of the candidate pool. Does not restrict manually forced allocations. Defaults to False.
        ignore_buses (list/str, optional): Bus name or list of bus names to be excluded from the random allocation candidate pool (e.g., ['150', '610']). Defaults to None.
    Returns:
        PVGen: A list of configured and interpolated PVGenerator objects.
    """

    # Initialize OpenDSS interface and compile the target circuit
    dss = py_dss_interface.DSS()
    dss.text(f"compile '{SCRIPT_DSS}'")

    # Check for compilation success using the OpenDSS error code
    if dss.errorinterface.error_code == 0:
        print("Success: Circuit compiled.")
    else:
        # Raise an exception to stop execution immediately
        raise RuntimeError(f"OpenDSS Compilation Failed: {dss.errorinterface.error_desc}")

    # Set internal seed for reproducibility
    seed(my_seed)

    # Initialize PV dictionaries list and handle bus mapping logic
    # If no list is provided, start with an empty one
    if  PV_dictionaries_list is None:
        PV_Dictionaries = []
        Existent_PV_buses = pd.DataFrame(columns=['bus'])
    else:
        PV_Dictionaries = PV_dictionaries_list
        
        # If multiple PVs per bus are not allowed, extract already occupied buses
        if not bus_multi_PV:
            # Using list comprehension to extract the 'PV_bus' attribute from each dictionary
            Existent_PV_buses = pd.DataFrame({'bus': [dictionary['PV_bus'] for dictionary in PV_Dictionaries]})
        else:
            Existent_PV_buses = pd.DataFrame(columns=['bus'])

    # Initialize support lists for mapping available buses from the circuit
    PV_buses = []
    PV_buses_kv = []
    PV_buses_phases = []

    # Iterate through circuit buses to identify eligible connection points
    print("Mapping available buses...")
    for i in dss.circuit.buses_names:
        dss.circuit.set_active_bus(i)
        if dss.bus.name.isdigit():
            # Define connection and phase count based on bus topology (nodes)
            if len(dss.bus.nodes) == 1:
                PV_buses.append(f"{dss.bus.name}.{dss.bus.nodes[0]}")
                PV_buses_phases.append(1)
            elif len(dss.bus.nodes) == 2:
                # Randomly select one of the available nodes for single-phase connection
                PV_buses.append(f"{dss.bus.name}.{choice(dss.bus.nodes)}")
                PV_buses_phases.append(1)
            elif len(dss.bus.nodes) == 3:
                PV_buses.append(f"{dss.bus.name}.{dss.bus.nodes[0]}.{dss.bus.nodes[1]}.{dss.bus.nodes[2]}")
                PV_buses_phases.append(3)
            PV_buses_kv.append(round(dss.bus.kv_base, 2))
    
    # Create candidate DataFrame and perform random bus sampling
    allbuses = pd.DataFrame({'bus': PV_buses, 'L-N kv': PV_buses_kv, 'phases': PV_buses_phases})

    if ignore_buses is not None:
        # If the user passed a single string (e.g., ignore_buses='150'), convert it to a list
        if isinstance(ignore_buses, str):
            ignore_buses = [ignore_buses]
            
        # Extract the pure bus name (before the dot) and filter out the ignored ones
        # e.g., '150.1.2.3' becomes '150' and matches the ignore list
        allbuses = allbuses[~allbuses['bus'].str.split('.').str[0].isin(ignore_buses)]
        print(f"Applied filter: Excluded {len(ignore_buses)} bus(es) from the candidate pool.")

    # Perform unique bus filtering if multi-PV is disabled
    available_buses = allbuses[~allbuses['bus'].isin(Existent_PV_buses['bus'])] if not bus_multi_PV else allbuses
    available_buses = available_buses.reset_index(drop=True)

    if len(available_buses) < QtdPVs:
        raise ValueError(f"Error: Not enough available buses to allocate {QtdPVs} PV systems. Only {len(available_buses)} buses are available.")

    PVbuses = available_buses.sample(n=QtdPVs, random_state=my_seed)

    # Check if manual PV configurations were provided
    if PV_Dictionaries:
        manual_count = len(PV_Dictionaries)
        print(f"Manually defined {manual_count} PV generators from input list.")
    else:
        print("No manual PV configurations detected. Proceeding with random allocation only.")

    print(f"Randomly selected {QtdPVs} buses for PV installation.")

    print(f"{((QtdPVs + len(PV_Dictionaries))/len(available_buses))*100:.2f}% of available buses allocated for PV systems.")
    print(f"{(QtdPVs + len(PV_Dictionaries))} buses occupied out of {len(available_buses)} total available buses.")

    # Populate technical configurations for each PV generator based on the sampled buses
    for bus in PVbuses.index:
        PV_Dictionaries.append({
            'PV_phases': (int(PVbuses.loc[bus, 'phases'])),
            'PV_bus': (PVbuses.loc[bus, 'bus']),
            # Voltage: kV base for 1-phase, kV L-L (base * sqrt(3)) for 3-phase
            'PV_kv': float(((PVbuses.loc[bus, 'L-N kv']) if (PVbuses.loc[bus, 'phases']) == 1 else round(((PVbuses.loc[bus, 'L-N kv'])*(3**(1/2))), 2))),
            'PV_kva': None,
            'PV_curve_id':None,
            'npts_origin': npts_origin})
    
    # Initialize the list for generator objects
    PVGen = []

    # Instantiate converters and apply temporal resampling (interpolation)
    print(f"Starting PV generation and {step} interpolation...")
    for PV, PV_data in enumerate(PV_Dictionaries):
        new_pv = PVGenerator(
            PV_id = PV+1,
            PV_phases = PV_data['PV_phases'],
            PV_bus = PV_data['PV_bus'],
            PV_kv = PV_data['PV_kv'],
            PV_kva = PV_data['PV_kva'],
            PV_curve_id = PV_data['PV_curve_id'],
            npts_origin = PV_data['npts_origin'],
            PV_list = PV_list
        )
        # Resample curves to the simulation time step (step)
        new_pv.CurveLinearInterpolation(step)
        PVGen.append(new_pv)
        print(f"  > {new_pv.name} configured at bus {new_pv.bus} ({new_pv.kva} kVA)")
    return PVGen

class PVGenerator:
    def __init__(
            self,  
            PV_kv, 
            PV_kva,
            PV_bus:str,
            PV_phases:int,
            PV_id:int, 
            PV_curve_id:int, 
            npts_origin:int, 
            PV_list:pd.DataFrame, 
            start:int=96
            ):
        
        """
        Initializes the PV generator by mapping technical parameters to the solar dataset.

        Args:
            PV_kv (float): Phase voltage at the connection bus.
            PV_kva (float): Installed PV capacity (kVA).
            PV_bus (str): Bus identifier for connection.
            PV_phases (int): Number of phases for the connection.
            PV_id (int): Unique integer ID for generator naming.
            PV_curve_id (int): ID for curve file selection (range 1-51).
            npts_origin (int): Original number of points (15-min resolution).
            PV_list (pd.DataFrame): Metadata DataFrame containing plant information.
            start (int): Starting index for data slicing, skipping previous points.
        """

        # --- CURVE ID CONFIGURATION & VALIDATION ---
        # Set curve_id using PV_id as fallback if curve_id is NaN
        self.curve_id = PV_id if pd.isna(PV_curve_id) else PV_curve_id
        
        # Ensure curve_id remains within the valid dataset range (1 to 51)
        if self.curve_id > 51:
            self.curve_id = int(float(self.curve_id) % 51)
        elif self.curve_id <= 0:
            print(f'\nWARNING: Input PV id was {PV_curve_id}. Must be >= 1. Defaulting to 1.')
            self.curve_id = 1

        # --- SOLAR CURVE FILE LOADING ---
        # Locate and load the CSV file corresponding to the defined curve_id
        self.curve = PV_list.iloc[self.curve_id-1, 1]
        self.FILE_CSV = self.curve + '.csv'
        self.SOLAR_STATION_FILE = SOLAR_STATION_FILES/self.FILE_CSV

        try:
            self.solar_station_curves = pd.read_csv(self.SOLAR_STATION_FILE)
        except FileNotFoundError:
            raise FileNotFoundError(f"Error: Dataset file {self.SOLAR_STATION_FILE} not found.")

        # --- BASIC PV ATTRIBUTES ---
        # Naming, phase count, bus connection, voltage, and capacity
        self.name = 'PV'+str(PV_id)
        self.phases = PV_phases
        self.bus = PV_bus
        self.kv = PV_kv
        
        # KVA Setup: Use metadata if PV_kva is NaN. Scale by 3 for 3-phase systems.
        # If PV_kva is not provided, fetch from metadata (and convert to VA)
        if pd.isna(PV_kva):
            base_kva = int(PV_list.iloc[self.curve_id-1, 3]) * 1000
            # Scale by 3 for three-phase systems when using baseline metadata
            self.kva = base_kva * 3 if PV_phases == 3 else base_kva
        else:
            # Use the manually defined capacity directly
            self.kva = int(PV_kva)

        # --- ELECTRICAL & THERMAL PANEL PARAMETERS ---
        # Base irradiance, max power (Pmpp), reference temperature, and power factor
        self.irrad = 0.8 * 1000
        self.pmpp = self.kva
        self.temperature = 25
        self.pf = 1
        self.vminpu = 0.001
        self.model = 1

        # --- EFFICIENCY & POWER CORRECTION CURVES ---
        # Define characteristic curves for inverter efficiency and PV temperature correction
        self.effcurve = 'New XYCurve.MyEff npts=4 xarray=[0.1, 0.2, 0.4, 1.0] yarray=[0.86, 0.90, 0.93, 0.97]'
        self.ptcurve = 'New XYCurve.MyPvsT npts=4 xarray=[0, 25, 75, 100] yarray=[1.2, 1.0, 0.8, 0.6]'

        # --- CURVES PROCESSING ---
        self.npts = npts_origin
        data_slice = slice(start, self.npts + start + 1)
        
        # 1. Process Irradiance (Normalize, clip negatives, fill NaNs)
        self.irrad_curve = (self.solar_station_curves['poa_irradiance_wm2'].iloc[data_slice] / self.irrad).reset_index(drop=True)
        self.irrad_curve = self.irrad_curve.clip(lower=0).fillna(0)
        self.irrad_curve.name = f'my_shape{PV_id}_irrad'

        # 2. Process Temperature (Normalize, fill NaNs)
        self.temperature_curve = (self.solar_station_curves['panel_temperature_celsius'].iloc[data_slice] / self.temperature).reset_index(drop=True)
        self.temperature_curve = self.temperature_curve.fillna(1)
        self.temperature_curve.name = f'my_shape{PV_id}_temperature'

        # 3. Handle Datetime & Indexing
        # Convert timestamp strings to datetime objects and reset index to align (0-based)
        self.datetime = pd.to_datetime(self.solar_station_curves['datetime'].iloc[data_slice]).reset_index(drop=True)

        # Concatenate the datetime column with the curves
        self.irrad_curve = pd.concat([self.datetime, self.irrad_curve], axis=1)
        self.temperature_curve = pd.concat([self.datetime, self.temperature_curve], axis=1)

        # Set 'datetime' as the index. 
        self.irrad_curve = self.irrad_curve.set_index('datetime')
        self.temperature_curve = self.temperature_curve.set_index('datetime')

    def CurveLinearInterpolation(self, new_rate=step, npts_base_15min=npts_origin, start_date=start_date):
        """
        Resamples a time-series curve to a new time frequency using linear interpolation.
        
        Args:
            new_rate (str): Pandas offset alias for frequency (e.g., '5s', '1h', '15min').
        """

        # Define Timedelta parameters natively to handle any scale (seconds, minutes, hours)
        base_delta = pd.Timedelta('15min')
        new_delta = pd.Timedelta(new_rate)
        
        # Calculate expected array size dynamically
        expected_points = ceil(npts_base_15min * (base_delta / new_delta))

        # --- RESAMPLING & LINEAR INTERPOLATION ---
        # 1. resample: Groups data into the new time interval (new_rate)
        # 2. mean: Aggregates points for downsampling or creates NaNs for upsampling
        # 3. interpolate: Fills gaps using time-proportional linear connection
        self.irrad_curve = (self.irrad_curve.resample(new_rate).mean().interpolate(method='time')).round(6)
        self.temperature_curve = (self.temperature_curve.resample(new_rate).mean().interpolate(method='time')).round(6)
        
        # Discard the temporary anchor points using structural slicing
        self.irrad_curve = self.irrad_curve.iloc[:expected_points]
        self.temperature_curve = self.temperature_curve.iloc[:expected_points]

        # Generate a clean sequential timeline starting exactly at START_DATE matching the required points
        new_timeline = pd.date_range(start=start_date, periods=expected_points, freq=new_rate)
        
        # Assign the new timeline back as the dataframe index
        self.irrad_curve.index = new_timeline
        self.temperature_curve.index = new_timeline

        # Reset index to restore numerical indexing and convert time back to a column
        self.irrad_curve = self.irrad_curve.reset_index()
        self.temperature_curve = self.temperature_curve.reset_index()

    @staticmethod
    def GenerateCSV(PVGen, OUTPUT_DIR = OUTPUT_DIR):
        """
        Consolidates and exports irradiance and temperature curves from all PV generators to CSV.
        
        Args:
            PVGen (list): List of PVGenerator instances. Defaults to global PVGen.
            OUTPUT_DIR (Path/str): Destination directory. Defaults to global OUTPUT_DIR.
        """

        print("Consolidating curves into CSV files...")
        # 1. Consolidate Irradiance Curves
            # Combine the first generator (serving as a time-base 'locomotive' with datetime) 
            # with only the data columns (iloc[:, 1]) from all remaining generators. 
            # This list-based approach is memory-efficient for large-scale grid simulations.
        irrad_list = [PVGen[0].irrad_curve] + \
                    [pv.irrad_curve.iloc[:, 1] for pv in PVGen[1:]]

        all_irrad_curves = pd.concat(irrad_list, axis=1)

        # 2. Consolidate Temperature Curves
        temp_list = [PVGen[0].temperature_curve] + \
                    [pv.temperature_curve.iloc[:, 1] for pv in PVGen[1:]]

        all_temperature_curves = pd.concat(temp_list, axis=1)

        # 3. Export to CSV
        all_irrad_curves.to_csv(OUTPUT_IRRAD_CSV, index=False)
        all_temperature_curves.to_csv(OUTPUT_TEMP_CSV, index=False)
        print(f"  Success: CSV files saved to {OUTPUT_DIR}")

    @staticmethod
    def GenerateDSS(PVGen, OUTPUT_DIR=OUTPUT_DIR):
        """
        Generates an OpenDSS script file defining all PVSystems.
        
        Args:
            PVGen (list): List of PVGenerator instances.
            OUTPUT_DIR (Path/str): Destination directory for the .dss file.
        """

        print("Generating OpenDSS script...")
        # We use a list to collect lines for better performance (string building)
        dss_lines = []

        # 1. Add base curves shared by all PV units (from the first generator)
        # Using f-strings without excessive (+) concatenation for clarity
        dss_lines.append(f"{PVGen[0].ptcurve}")
        dss_lines.append(f"{PVGen[0].effcurve}\n")

        # 2. Build commands for each PV generator
        for i, pv in enumerate(PVGen):
            pv_id = i + 1
            
            # Constructing the multi-line OpenDSS command using a single f-string
            # Note: ~ is the OpenDSS line continuation character
            pv_command = (
                f"New PVSystem.{pv.name} phases={pv.phases} Bus1={pv.bus} "
                f"kV={pv.kv} kVA={pv.kva} irrad={pv.irrad/1000} Pmpp={pv.pmpp}\n"
                f"~ temperature={pv.temperature} PF={pv.pf} EffCurve=MyEff P-TCurve=MyPvsT\n"
                f"~ Daily=my_shape{pv_id}_irrad TDaily=my_shape{pv_id}_temperature\n"
                f"~ Vminpu={pv.vminpu} Model={pv.model}\n"
            )
            dss_lines.append(pv_command)

        # 3. Write the file using pathlib
        with open(OUTPUT_DSS_FILE, "w") as f:
            # Join all lines with a newline separator
            f.write("\n".join(dss_lines))
        print(f"  Success: 'data_pv.dss' saved to {OUTPUT_DIR}")

# Model of list of PVs to be created, with the possibility of predefining some parameters
# and letting the function fill in the rest. This is useful for testing and for cases where
# we want to ensure certain configurations are included.
#
# Dictionary Parameters:
# - PV_phases: Integer defining the number of phases (e.g., 1 for single-phase, 3 for three-phase).
# - PV_bus: String representing the bus name and its nodes (e.g., '29.1.2.3').
# - PV_kv: Float specifying the nominal voltage level in kV at the connection point. L-L voltage for three-phase systems and L-N voltage for single-phase systems.
# - PV_kva: Float defining the rated power capacity (kVA) of the PV inverter.
# - PV_curve_id: String or None; identifies a specific irradiance/temperature curve to be assigned.
# - npts_origin: Integer indicating the number of points in the original time series data.
PV_Dictionaries = [
    {'PV_phases': 3, 'PV_bus': '646.1.2.3', 'PV_kv': 4.16, 'PV_kva': 5000, 'PV_curve_id': None, 'npts_origin': npts_origin}
]

PVGen = PVCreator(QtdPVs=4, PV_dictionaries_list=PV_Dictionaries, ignore_buses=['650', '670'])

#PVGen = PVCreator(QtdPVs=2)
PVGenerator.GenerateCSV(PVGen)
PVGenerator.GenerateDSS(PVGen)

