#!/usr/local/bin/python3.8

#######################################################################################################
### Script to parse the InterOp binary files using the Python bindings provided by
### Illumina for their InterOp Library (https://github.com/Illumina/interop)
###
### Script to extract Lane and Run level metrics from the InterOp binary files (QC reporting purpose)
###	Additonally tile level plots are generated, akin to the visualization in Illumina's SAV software.
###
### Sirisha Sunkara, Nov 12 2019
###
###
######################################################################################################

import sys
import getopt
import os
import re
import pandas as pd
import collections
import numpy as np
import matplotlib.pyplot as plt
from interop import py_interop_run_metrics
from interop import py_interop_run
from interop import py_interop_table
from interop import py_interop_metrics
from interop import py_interop_plot
from interop import py_interop_comm
from interop import py_interop_summary


def main(argv):

	if (len(argv) < 3):
		print ('InterOpParser.py -s <StreamingPath> -t <FlowcellType>')
		sys.exit(2)

	StreamingPath = ''
	FlowcellType = ''

	try:
		opts, args = getopt.getopt(argv, "hs:t:", ["streaming_path=", "type="]);
		
	except getopt.GetoptError:
		print ('InterOpParser.py -s <StreamingPath> -t <FlowcellType>')
		sys.exit(2)
		
	for opt, arg in opts:
		if opt == "-h":
			print ('InterOpParser.py -s <StreamingPath> -t <FlowcellType>')
			sys.exit()
		elif opt in ("-s", "--streaming_path"):
			StreamingPath = arg
		elif opt in ("-t", "--type"):
			FlowcellType = arg
		
	if not os.path.isdir(os.path.join(StreamingPath, 'InterOp')):
		print ("InterOp directory not found within {} folder", StreamingPath)
	
	calculate_Lane_Metrics(StreamingPath)
	
	generate_Tile_Plots(StreamingPath, FlowcellType)
	

	

def format_value(val):

    if hasattr(val, 'mean'):
        return val.mean()
    else:
        return val
	
	
	
def calculate_Lane_Metrics(StreamingPath):
	
	### Capture specific metrics from the Interop binary files
	
	run_metrics = py_interop_run_metrics.run_metrics()
	valid_to_load = py_interop_run.uchar_vector(py_interop_run.MetricCount, 0)
	py_interop_run_metrics.list_summary_metrics_to_load(valid_to_load)
	run_metrics.read(StreamingPath, valid_to_load)
	summary = py_interop_summary.run_summary()
	py_interop_summary.summarize_run_metrics(run_metrics, summary)
	columns = ( ('Lane', 'lane'), ('Density (K/mm2)', 'density'), ('ClustersPF', 'percent_pf'), ('Percent >= Q30', 'percent_gt_q30'), ('ErrorRate', 'error_rate'), \
	            ('ErrorRate35Cycles', 'error_rate_35'), ('ErrorRate50Cycles', 'error_rate_50'), ('ErrorRate75Cycles', 'error_rate_75'), ('ErrorRate100Cycles', 'error_rate_100') )  
		    
		    	
	reads = [0,3]					### Report the lane metrics on the non-index reads for the NovaSeqs in this version of the parser.
	for read in reads:
		rows = [summary.at(read).at(lane) for lane in range(summary.lane_count())]
		d = []
		d.append(("Read", read+1))
		
		for label, func in columns:
			d.append( (label, pd.Series([format_value(getattr(r, func)()) for r in rows])) )
		
		lane_df = pd.DataFrame.from_dict(collections.OrderedDict(d))
		lane_json = lane_df.to_json(orient='records')
		with open('RunCompletion.json', 'a+') as f:
			f.write(lane_json)
			f.write("\n")
			
	
	### Run level metrics only
		
	run_d = []
	run_rows = [('Non-Indexed Total', summary.nonindex_summary()), ('Total', summary.total_summary())]
	
	run_d.append( ('Yield Total (G)', pd.Series([getattr(r[1], "yield_g")() for r in run_rows], index=[r[0] for r in run_rows])))
	run_df = pd.DataFrame.from_dict(collections.OrderedDict(run_d))
	yield_json = run_df.to_json(orient='index')
		
	with open('Yield.json', 'w') as y:		### Rewrite this to report within the RunCompleteion.json
		y.write(yield_json)
		
	#return lane_df.values.tolist()
	
	
	
	
def generate_Tile_Plots(StreamingPath, FlowcellType):

	valid_to_load = py_interop_run.uchar_vector(py_interop_run.MetricCount, 0)
	valid_to_load[py_interop_run.ExtendedTile] = 1
	valid_to_load[py_interop_run.Tile] = 1
	valid_to_load[py_interop_run.Extraction] = 1
	
	run_metrics = py_interop_run_metrics.run_metrics()
	run_metrics.read(StreamingPath, valid_to_load)
	columns = py_interop_table.imaging_column_vector()
	py_interop_table.create_imaging_table_columns(run_metrics, columns)
	
	headers = []
	for i in range(columns.size()):
		column = columns[i]
		
		if column.has_children():
			headers.extend([column.name()+"("+subname+")" for subname in column.subcolumns()])
		else:
			headers.append(column.name())
	
	column_count = py_interop_table.count_table_columns(columns)
	row_offsets = py_interop_table.map_id_offset()
	py_interop_table.count_table_rows(run_metrics, row_offsets)
	
	data = np.zeros((row_offsets.size(), column_count), dtype=np.float32)
	py_interop_table.populate_imaging_table_data(run_metrics, columns, row_offsets, data.ravel())
	
	header_subset = ["Lane", "% Occupied", "% Pass Filter"]
	header_index = [(header, headers.index(header)) for header in header_subset]
	ids = np.asarray([headers.index(header) for header in header_subset[:3]])
	
	d = []
	for label, col in header_index:
		d.append( (label, pd.Series([val for val in data[:, col]], index=[tuple(r) for r in data[:, ids]])))
	
	tile_df = pd.DataFrame.from_dict(dict(d))
	
	
	#### Plotting code
	#ymin = (int((tile_df["% Pass Filter"].min()))%10) * 10
	ymin = (int((tile_df["% Pass Filter"].min())/10)) * 10 - 10
	#xmin = (int((tile_df["% Occupied"].min()))%10) * 10
	xmin = (int((tile_df["% Occupied"].min())/10)) * 10 - 10
	plt.scatter(tile_df["% Occupied"], tile_df["% Pass Filter"])
	plt.yticks(np.arange(ymin, 101, 10))
	plt.xticks(np.arange(xmin, 101, 10))
	plt.xlabel('% Occupied')
	plt.ylabel('% Pass Filter')
	
	StreamingPath = re.sub('/$', '', StreamingPath)
	
	plt.savefig(os.path.basename(StreamingPath) + "_" + FlowcellType + '.png')
	
	
			

if __name__ == "__main__":
	main(sys.argv[1:])

 
