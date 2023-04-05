#####################################################################################
##### Data migration tool to transfer data from on-prem to genedata datalake
##### Sirisha Sunkara; 01/18/2023
##### gdp client needs to be setup on-prem to talk to either the dev. or prod. server
#####################################################################################

import pandas as pd
import xmltodict
import re
import subprocess
import argparse
import configparser
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--file", type=str, required=True)
parser.add_argument(
    "--parent_folder", type=str, default="folder-1ff52e14-05a2-448c-a745-fd9654989b00"
)
parser.add_argument("--xml", type=str, required=True)
args = parser.parse_args()

masterfile = args.file
parent_folder = args.parent_folder
xmlfile = args.xml

gdpclient = "/export/home/ssunkara1/.python3.8/bin/gdp"


############################################################################
#### Read config.ini file
#### config.ini maps the fields in the xml to the metadata.csv column names
#### config.optionxform = str to retain case
############################################################################

config = configparser.RawConfigParser()
config.optionxform = str
config.read("config.ini")
config_dict = dict(config.items("PROD"))

###############################################################
#### Extract attributes from xml
###############################################################
with open(xmlfile, "r") as xml_obj:
    xml_dict = xmltodict.parse(xml_obj.read())
    xml_obj.close()

attributecount = len(xml_dict["MetadataRules"]["Rule"])
metadatadict = {}

for _ in range(1, attributecount):
    metadatadict[xml_dict["MetadataRules"]["Rule"][_]["@attributeName"]] = xml_dict[
        "MetadataRules"]["Rule"][_]["Dictionary"]["Item"]


def parse_metadata(met, metadatadict):
    project_dict = {}
    metadata_csv = pd.read_csv(met, encoding="windows-1254")

    for (
        attrname
    ) in (
        metadatadict.keys()
    ):  #### For each attribute in the xml file, run through the attibute values
        metadatafileCol = config_dict[attrname]
        if (
            metadatafileCol
        ):  #### If corresponding column was mappable to the metadata.csv column
            if (
                metadatafileCol in metadata_csv
            ):  #### Not all metadata columns exist in all metadata.csv files
                for attrval in metadatadict[attrname]:
                    if re.search(str(metadata_csv[metadatafileCol][0]), attrval, re.I):
                        project_dict[repr(attrname)] = repr(attrval)
        elif attrname == "Access Tag":
            project_dict[repr("Access Tag")] = "Internal"
        else:
            project_dict[attrname] = ""

    return project_dict


#############################################################################################
#### Read info from Ruidong's project masterfile
#### Expected format: Project,Data Type,Count Matrix,Sample Metadata
#### Additional implementation - if folder in datalake already exists, do not create another
#############################################################################################
with open(masterfile, "r") as master:
    for line in master.readlines():
        if re.search("^SCL", line):
            project, dattype, countmat, metadat = line.strip().split(",")
            countfiles = countmat.split("\t")
            metadatfiles = metadat.split("\t")

            foldersearch = f'gdp data search "Name = {project}" -o "id"'
            createfolder = f"gdp data mkdir --folder-id {parent_folder} {project}"
            cdfolder = f"gdp data cd --folder-id {parent_folder} {project}"

            subprocess.run(["gdp clear"], shell=True)
            folderid = subprocess.run(
                foldersearch, shell=True, capture_output=True, encoding="utf-8"
            )

            if folderid.returncode != 0:
                subprocess.run(createfolder, shell=True)
                subprocess.run(cdfolder, shell=True)

            if metadat:
                for met in metadatfiles:
                    project_dict = parse_metadata(met, metadatadict)
                    cpmet = f"gdp data upload -m 'SCL Project Id'={project}"

                    for projectkey in project_dict:
                        if project_dict[projectkey]:
                            cpmet += f" -m {projectkey}={project_dict[projectkey]}"
                    cpmet += f" {met}"

                    subprocess.run(cpmet, shell=True)

                ### If the metadata.csv file is available, extract the tags for the count.txt from the metadata.csv
                if countmat:
                    for count in countfiles:
                        cpcount = f"gdp data upload -m 'SCL Project Id'={project}"
                        for projectkey in project_dict:
                            if project_dict[projectkey]:
                                cpcount += (
                                    f" -m {projectkey}={project_dict[projectkey]}"
                                )
                        cpcount += f" {count}"

                        subprocess.run(cpcount, shell=True)

            elif (
                countmat
            ):  ### If only count matrix files are available, upload them with hard-coded metadata tags for now
                for count in countfiles:
                    cpcount = (
                        f'gdp data upload -m "SCL Project Id"={project}'
                        f' -m "Access Tag"="Internal"'
                        f' -m "Analyte"="RNA"'
                        f' -m "Sequencing Application"="mRNA-seq"'
                        f' -m "Sequencing Platform"="Illumina"'
                        f' -m "Data Source"="Gilead Sequencing Core"'
                        f' -m "Analysis Type"="Bulk RNASeq"'
                        f" {count}"
                    )
                    subprocess.run(cpcount, shell=True)
            else:
                print(f"No Files to upload for {project}")
