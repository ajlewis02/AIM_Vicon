#!/usr/bin/env python
# //==============================================================================
# /*
#     Software License Agreement (BSD License)
#     Copyright (c) 2020, AIMVicon
#     (www.aimlab.wpi.edu)

#     All rights reserved.

#     Redistribution and use in source and binary forms, with or without
#     modification, are permitted provided that the following conditions
#     are met:

#     * Redistributions of source code must retain the above copyright
#     notice, this list of conditions and the following disclaimer.

#     * Redistributions in binary form must reproduce the above
#     copyright notice, this list of conditions and the following
#     disclaimer in the documentation and/or other materials provided
#     with the distribution.

#     * Neither the name of authors nor the names of its contributors may
#     be used to endorse or promote products derived from this software
#     without specific prior written permission.

#     THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
#     "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
#     LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
#     FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
#     COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
#     INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
#     BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
#     LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
#     CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
#     LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
#     ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
#     POSSIBILITY OF SUCH DAMAGE.

#     \author    <http://www.aimlab.wpi.edu>
#     \author    <nagoldfarb@wpi.edu>
#     \author    Nathaniel Goldfarb
#     \version   0.1
# */
# //==============================================================================
import csv
from typing import List, Any

import csv
from typing import List, Any

import pandas

from ..Interpolation import Akmia
import numpy as np
from Vicon.Markers import ModelOutput as modeloutput
from Vicon.Devices import EMG, IMU, Accel, ForcePlate
from . import MocapBase
import matplotlib.pyplot as plt
from ..Markers import Markers as markers

from Vicon import Markers

## @package Vicon
# Reads motion capture data from a csv file.

## @class Vicon
# Object to read motion capture data
#
# Will read data from `file_path` on construction. May take a few seconds for large datasets!
class ViconOld(object):

    ## Vicon constructor
    # @param file_path The file to read from
    # @param verbose Flag to enable status prints, defaults to False
    # @param interpolate Flag to enable interpolating holes in data, defaults to True
    # @param maxnanstotal Configures the maximum total missing data points that Vicon will attempt to interpolate
    # @param maxnansrow Configures the maximum missing data points in a row that Vicon will attempt to interpolate
    # @param sanitize Flag to replace any dataset consisting solely of NaNs with 0s, defaults to True
    def __init__(self, file_path, verbose=False, interpolate=True, maxnanstotal=-1, maxnansrow=-1, sanitize=True):
        self._file_path = file_path
        self.joint_names = ["Ankle", "Knee", "Hip"]
        self._number_of_frames = 0
        self._T_EMGs = {}
        self._EMGs = {}
        self._force_plates = {}
        self._IMUs = {}
        self._accels = {}

        #  nan_dict is a dictionary with the same format of data_dict,
        #  but it keeps track of the positions of nans that get interpolated.

        #  data is accessed through nan_dict[category][subject][field],
        #  where nan_dict contains category iff there is at least one valid subject for the category,
        #  nan_dict[category] contains subject iff there is at least one valid field for the subject, and
        #  nan_dict[category][subject] contains field iff data_dict[category][subject][field]["data"] exists.

        #  nan_dict[category][subject][field] is a boolean array where
        #  nan_dict[category][subject][field] = np.isnan(data_dict[category][subject][field]["data"])
        #  or, nan_dict[category][subject][field][n] = np.isnan(data_dict[category][subject][field]["data"][n])
        #  iff data_dict[category][subject][field]["data"] contained missing values that were interpolated.

        #  if data_dict[category][subject][field]["data"] did not contain any missing values,
        #  or if data_dict[category][subject][field]["data"] consisted solely of nans,
        #  nan_dict[category][subject][field] is an array consisting only of False,
        #  where len(nan_dict[category][subject][field]) = len(data_dict[category][subject][field]["data"])

        self._nan_dict = {}

        #  sanitized is a dictionary to keep track of what subject, if any, have had their fields sanitized
        #  If sanitized[category][subject] exists, that subject has had at least one field sanitized
        self._sanitized = {}

        self.data_dict = self.open_vicon_file(self._file_path, verbose=verbose, interpolate=interpolate,
                                              maxnanstotal=maxnanstotal, maxnansrow=maxnansrow, sanitize=sanitize)
        self._make_Accelerometers(verbose=verbose)
        self._make_EMGs(verbose=verbose)
        self._make_force_plates(verbose=verbose)
        self._make_IMUs(verbose=verbose)
        self._make_marker_trajs()
        self._make_model(verbose=verbose)

    ## Finds the number and sets of frames
    # @param col The column to search in
    def _find_number_of_frames(self, col):
        """
        Finds the number and sets of frames
        :param col: column to search in
        :return: None
        """
        index = col.index("Frame") + 2
        current_number = col[index]

        while current_number.isdigit():
            index += 1
            current_number = col[index]

        self.number_of_frames = col[index - 1]

    @property
    ## Returns the dataset's markers
    def markers(self):
        return self._markers

    @property
    ## Returns the dataset's length
    def length(self):
        return self._length

    @length.setter
    ## Sets the dataset's length
    def length(self, value):
        self._length = value

    @property
    ## Returns the number of frames
    def number_of_frames(self):
        """

        :return: number of frames
        :rtype: int
        """
        return self._number_of_frames

    @number_of_frames.setter
    ## Sets the number of frames
    def number_of_frames(self, value):
        """

        :param value:
        :return:
        """
        self._number_of_frames = value

    @property
    ## Returns the Accels dictionary
    def accels(self):
        """
        Get the Accels dict
        :return: Accels
        :type: dict
        """
        return self._accels

    @property
    ## Returns the Force Plate dictionary
    def force_plate(self):
        """
         Get the force plate dict
         :return: Force plates
         :type: dict
        """
        return self._force_plates

    @property
    ## Returns the IMU dictionary
    def IMUs(self):
        """
         Get the IMU dict
         :return: IMU
         :type: dict
        """
        return self._IMUs

    @property
    ## Returns the T EMG dictionary
    def T_EMGs(self):
        """
         Get the EMG dict
         :return: T EMG
         :type: dict
        """
        return self._T_EMGs

    @property
    ## Returns the EMG dictionary
    def EMGs(self):
        """
        Get the EMGs dict
        :return: EMGs
        :type: dict
        """
        return self._EMGs

    ## Returns the model output
    def get_model_output(self):
        """
        get the model output
        :return: model outputs
        :rtype: ModelOutput.ModelOutput
        """
        return self._model_output

    ## Returns the segments
    def get_segments(self):
        """
        get the segments
        :return: model segments
        :type: dict
        """
        return self.data_dict["Segments"]

    ## Returns the keys to the segments dictionary
    def get_segments_keys(self):
        """
        get the segments
        :return: model segments keys
        :type: list of keys
        """
        return self.data_dict.keys()

    ## Returns the markers
    def get_markers(self):
        """
        get the markers
        :return: markers
        :type: dict
        """
        return self.markers

    ## Returns the joints
    def get_joints(self):
        """
        get the joints
        :return: model joints
        :type: dict
        """
        return self.data_dict["Joints"]

    ## Returns the keys to the joints dictionary
    def get_joints_keys(self):
        """
        get the joints keys
        :return: model joints keys
        :type: list of keys
        """
        return self.data_dict.keys()

    ## Returns an IMU of specified index
    # @param index The index of the IMU
    def get_imu(self, index):
        """
        get the a imu
        :param index: imu number
        :return: imu
        :type: IMU.IMU
        """
        return self.IMUs[index]

    def get_imu_keys(self):
        """
        get the imu keys
        :type: list
        """
        return self.IMUs.keys()

    def get_accel(self, index):
        """
        get the a Accel
        :param index: Accel number
        :return: Accel
        :type: Accel.Accel
        """
        return self.accels[index]

    def get_accel_keys(self):
        """
        get the a Accel keys
        :return: list of the keys
        :type: list
        """
        return self.accels.keys()

    def get_force_plate(self, index):
        """
        get the a force plate
        :param index: force plate number
        :return: Force plate
        :type: ForcePlate.ForcePlate
        """
        return self.force_plate[index]

    def get_force_plate_keys(self):
        """
        get the a force plate keys
        :return: list of keys
        :type: list
        """
        return self.force_plate.keys()

    def get_all_force_plate(self):
        """
        get the a force plate
        :return: Force plate
        :type: ForcePlate.ForcePlate
        """
        return self.force_plate

    def get_emg(self, index):
        """
       Get the EMG values
       :param index: number of sensor
       :return: EMG
       :rtype: EMG.EMG
        """
        return self._EMGs[index]

    def get_emg(self):
        """
       Get the EMG keys
       :return: list of keys
       :rtype: list
        """
        return self._EMGs.keys()

    def get_all_emgs(self):

        return self._EMGs

    def get_t_emg(self, index):
        """
        Get the T EMG values
        :param index: number of sensor
        :return: EMG
        :rtype: EMG.EMG
        """
        return self._T_EMGs[index]

    def get_t_emg_keys(self):
        """
        Get the T EMG keys
        :return: list of keys
        :rtype: list
        """
        return self._T_EMGs.keys()

    def get_all_t_emg(self, index):
        """
        Get the T EMG values
        :param index: number of sensor
        :return: EMG
        :rtype: EMG.EMG
        """
        return self._T_EMGs

    def _check_keys(self, key_list, key):
        """

        :param dict:
        :param key:
        :return:
        """

        return any(key in s for s in key_list)

    def _filter_number(self, key):
        """

        :param key:
        :return:
        """
        return int(''.join(filter(str.isdigit, key)))

    def _filter_dict(self, sensors, substring):
        """
        filter the dictionary
        :param sensors: Dictionary to parse
        :param substring: substring of the keys to look for in the dict
        :return: keys that contain the substring
        :type: list
        """
        my_list = []
        return list(filter(lambda x: substring in x, sensors.keys()))

    def _make_model(self, verbose=False):
        """
        generates a model from the model outputs
        :return:
        """
        if "Model Outputs" in self.data_dict:
            self._model_output = modeloutput.ModelOutput(self.data_dict["Model Outputs"])
            if verbose:
                print("Model Outputs generated")
        elif verbose:
            print("No Model outputs")

    def _make_force_plates(self, verbose=False):
        """
        generate force plate models
        :return: None
        """
        if "Devices" in self.data_dict:

            sensors = self.data_dict["Devices"]
            keys = self._filter_dict(sensors, 'Force_Plate')  # + ['Combined Moment'] + ['Combined CoP']

            if any("Force_Plate" in word for word in keys):
                key_numbers = set()
                for key in keys:
                    key_numbers.add(self._filter_number(key))

                for i in key_numbers:
                    self._force_plates[i] = ForcePlate.ForcePlate("Force_Plate_" + str(i),
                                                                  sensors["Force_Plate__Force_" + str(i)],
                                                                  sensors["Force_Plate__Moment_" + str(i)],
                                                                  sensors["Force_Plate__CoP_"+ str(i)])

                if verbose:
                    print("Force plate models generated")
            elif verbose:
                print("No force plates")
        elif verbose:
            print("A scan for force plates found no Devices")

    def _make_markers(self):
        markers = self.data_dict["Trajectories"]

    def _make_EMGs(self, verbose=True):
        """
        generate EMG models
        :return: None
        """
        if "Devices" in self.data_dict:
            sensors = self.data_dict["Devices"]
            all_keys = self._filter_dict(sensors, 'EMG')
            if len(all_keys) > 0:
                all_keys = self._filter_dict(sensors, 'EMG')
                T_EMG_keys = self._filter_dict(sensors, 'T_EMG')
                EMG_keys = [x for x in all_keys if x not in T_EMG_keys]
                for e_key, t_key in zip(EMG_keys, T_EMG_keys):
                    self._T_EMGs[self._filter_number(t_key)] = EMG.EMG(t_key, sensors[t_key]["EMG"])
                    self._EMGs[self._filter_number(e_key)] = EMG.EMG(e_key, sensors[e_key]["IM EMG"])
                if verbose:
                    print("EMG models generated")
            elif verbose:
                print("No EMGs")
        elif verbose:
            print("A scan for EMGs found no Devices")

    def _make_IMUs(self, verbose=False):
        """
        generate IMU models
        :return: None
        """
        if "Devices" in self.data_dict:
            sensors = self.data_dict["Devices"]
            keys = self._filter_dict(sensors, 'IMU')
            if len(keys) > 0:
                for key in keys:
                    self._IMUs[self._filter_number(key)] = IMU.IMU(key, sensors[key])
                if verbose:
                    print("IMU models Generated")
            elif verbose:
                print("No IMUs")
        elif verbose:
            print("A scan for IMUs found no Devices")

    def _make_marker_trajs(self):
        """
        generate IMU models
        :return: None
        """
        self._markers = markers.Markers(self.data_dict["Trajectories"], self._file_path[:len(self._file_path)-4])
        self._markers.make_markers()

    def _make_Accelerometers(self, verbose=False):
        """
        generate the accel objects
        :return: None
        """
        if "Devices" in self.data_dict:
            sensors = self.data_dict["Devices"]
            keys = self._filter_dict(sensors, 'Accel')
            if len(keys) > 0:
                for key in keys:
                    self._accels[self._filter_number(key)] = Accel.Accel(key, sensors[key])
                if verbose:
                    print("Accel models generated")
            elif verbose:
                print("No Accels")
        elif verbose:
            print("A scan for Accels found no Devices")

    def open_vicon_file(self, file_path, verbose=False, interpolate=True, maxnanstotal=-1, maxnansrow=-1,
                        sanitize=True):
        """
        parses the Vicon sensor data into a dictionary
        :param file_path: file path
        :param verbose: prints debug statements if True
        :return: dictionary of the sensors
        :rtype: dict
        """
        # open the file and get the column names, axis, and units
        if verbose:
            print("Reading data from file " + file_path)
        with open(file_path, mode='r') as csv_file:
            reader = csv.reader(csv_file)
            raw_data = list(reader)

        # output_names = ["Devices", "Joints", "Model Outputs", "Segments", "Trajectories"]
        data = {}
        names, segs = self._seperate_csv_sections(raw_data)

        for index, output in enumerate(names):
            data[output] = self._extract_values(raw_data, segs[index], segs[index + 1], verbose=verbose,
                                                category=output, interpolate=interpolate, maxnanstotal=maxnanstotal,
                                                maxnansrow=maxnansrow, sanitize=sanitize)

        return data

    def _seperate_csv_sections(self, all_data):
        """"""

        raw_col = []

        for row in all_data:
            if len(row) > 0:
                raw_col.append(row[0])
            else:
                raw_col.append("")

        fitlered_col: List[Any] = [item for item in raw_col if not item.isdigit()]
        fitlered_col = filter(lambda a: a != 'Frame', list(fitlered_col))
        fitlered_col = filter(lambda a: a != "", list(fitlered_col))
        fitlered_col = list(fitlered_col)
        if 'Devices' in fitlered_col:
            fitlered_col = fitlered_col[fitlered_col.index("Devices"):]

        inx = []
        for name in fitlered_col:
            inx.append(raw_col.index(name))

        inx.append(len(raw_col))
        return fitlered_col, inx

    def _fix_col_names(self, names):
        fixed_names = []
        get_index = lambda x: x.index("Sensor") + 7

        for name in names:  # type: str

            # if "Subject".upper() in name.upper():
            #     fixed = ''.join(
            #         [i for i in name.replace("Subject", "").replace(":", "").replace("|", "") if
            #          not i.isdigit()]).strip()
            #     fixed_names.append(fixed)

            if ":" in name:

                index = name.index(":")

                fixed_names.append(name[index + 1:])

            elif "AMTI" in name:

                if "Force" in name:
                    unit = "_Force_"
                elif "Moment" in name:
                    unit = "_Moment_"
                elif "CoP" in name:
                    unit = "_CoP_"

                number = name[name.find('#') + 1]
                fixed = "Force_Plate_" + unit + str(number)
                fixed_names.append(fixed)

            elif "Trigno EMG" in name:
                fixed = "T_EMG_" + name[-1]
                fixed_names.append(fixed)

            elif "Accelerometers" in name:
                fixed = "Accel_" + name[get_index(name):]
                fixed_names.append(fixed)

            elif "IMU AUX" in name:
                fixed = "IMU_" + name[get_index(name):]
                fixed_names.append(fixed)

            elif "IMU EMG" in name:
                fixed = "EMG_" + name[get_index(name):]
                fixed_names.append(fixed)
            else:
                fixed_names.append(name)

        return fixed_names

    def _extract_values(self, raw_data, start, end, verbose=False, category="", interpolate=True, maxnanstotal=-1,
                        maxnansrow=-1, sanitize=True):
        indices = {}
        data = {}
        current_name = None
        last_frame = None

        column_names = self._fix_col_names(raw_data[start + 2])

        # column_names = raw_data[start + 2]
        remove_numbers = lambda str: ''.join([i for i in str if not i.isdigit()])

        axis = list(map(remove_numbers, raw_data[start + 3]))
        unit = raw_data[start + 4]

        # Build the dict to store everything
        for index, name in enumerate(column_names):
            if index <= 1 or index >= len(axis):
                continue
            else:
                if len(name) > 0:
                    current_name = name

                    data[current_name] = {}
                dir = axis[index]
                indices[(current_name, dir)] = index
                data[current_name][dir] = {}
                data[current_name][dir]["data"] = []
                data[current_name][dir]["unit"] = unit[index]

        # Put all the data in the correct sub dictionary.

        flags = []

        # naninfo contains information on the total nans and max nans in a row within each field within each subject
        # naninfo[subject][field] exists for each subject and field that exists within the current category
        # naninfo[subject][field] is a dictionary which contains the keys "total", "row", "rowtemp", and "interpolate"
        # naninfo[subject][field]["total"] is the total number of nans detected within that field
        # naninfo[subject][field]["row"] is the highest number of nans in a row detected within that field
        # naninfo[subject][field]["rowtemp"] is used to calculate the "row" field and contains no useful data
        # naninfo[subject][field]["interpolate"] is a boolean value that determines if that field can be interpolated
        # according to the rules set by the user
        naninfo = {}
        for row in raw_data[start + 5:end - 1]:

            frame = int(row[0])

            for key, value in data.items():
                if key not in naninfo:
                    naninfo[key] = {}
                for sub_key, sub_value in value.items():
                    if sub_key not in naninfo[key]:
                        naninfo[key][sub_key] = {"total": 0, "row": 0, "rowtemp": 0}
                    index = indices[(key, sub_key)]
                    if index >= len(row) or row[index] == '' or str(row[index]).lower() == "nan":
                        val = np.nan
                        naninfo[key][sub_key]["total"] += 1
                        naninfo[key][sub_key]["rowtemp"] += 1
                    elif '!' in row[index]:
                        if naninfo[key][sub_key]["rowtemp"] > naninfo[key][sub_key]["row"]:
                            naninfo[key][sub_key]["row"] = naninfo[key][sub_key]["rowtemp"]
                        naninfo[key][sub_key]["rowtemp"] = 0
                        val = float(row[index][1:])
                        if verbose and (key, sub_key) not in flags:
                            print("Reading previously interpolated data in category " + category + \
                                  ", subject " + key + ", field " + sub_key + ".")
                            flags.append((key, sub_key))
                    else:
                        if naninfo[key][sub_key]["rowtemp"] > naninfo[key][sub_key]["row"]:
                            naninfo[key][sub_key]["row"] = naninfo[key][sub_key]["rowtemp"]
                        naninfo[key][sub_key]["rowtemp"] = 0
                        val = float(row[index])
                    sub_value["data"].append(val)

        for subject, fields in naninfo.items():
            for field, info in fields.items():
                if info["rowtemp"] > info["row"]:
                    # In fields where the last value is nan, the above loop doesn't properly set info["row"]
                    info["row"] = info["rowtemp"]
                if -1 < maxnanstotal < info["total"]:
                    info["interpolate"] = False
                    if verbose:
                        if field == "":
                            print("Field [Blank Name] in subject " + subject + " has " + str(info["total"]) +
                                  " nans, which violates the max nans rule of " + str(maxnanstotal) + " nans. [Blank " +
                                  " Name] will not be interpolated!")
                        else:
                            print("Field " + field + " in subject " + subject + " has " + str(info["total"]) +
                                  " nans, which violates the max nans rule of " + str(maxnanstotal) + " nans. " +
                                  field + " will not be interpolated!")
                elif -1 < maxnansrow < info["row"]:
                    info["interpolate"] = False
                    if verbose:
                        if field == "":
                            print("Field [Blank Name] in subject " + subject + " has " + str(info["row"]) +
                                  " nans in a row, which violates the max nans in a row rule of " +
                                  str(maxnansrow) + " nans in a row. [Blank Name] will not be interpolated!")
                        else:
                            print("Field " + field + " in subject " + subject + " has " + str(info["row"]) +
                                  " nans in a row, which violates the max nans in a row rule of " +
                                  str(maxnansrow) + " nans in a row. " + field + " will not be interpolated!")
                else:
                    info["interpolate"] = True

        for key, value in data.items():  # For every subject in the data...
            for sub_key, sub_value in value.items():  # For each field under each subject...
                #  If we have NaNs and the whole row isn't NaNs...
                #  No interpolation method can do anything with an array of NaNs,
                #  so this way we save ourselves a bit of computation
                nans = np.isnan(sub_value["data"])
                if True in nans and False in nans and interpolate and naninfo[key][sub_key]["interpolate"]:
                    if category not in self._nan_dict:
                        self._nan_dict[category] = {}
                    if key not in self._nan_dict[category]:
                        self._nan_dict[category][key] = {}
                    self._nan_dict[category][key][sub_key] = nans
                    if verbose:
                        print("Interpolating missing values in field " + sub_key + ", in subject " + key + \
                              ", in category " + category + "...")
                    s = pandas.Series(sub_value["data"])
                    #  Akima interpolation only covers interior NaNs,
                    #  and splines are *way* too imprecise with unset boundary conditions,
                    #  so linear interpolation is used for unset values at the edges
                    try:
                        s = s.interpolate(method='akima', limit_direction='both')
                    except ValueError:
                        if verbose:
                            print("Akima Interpolation failed for field " + sub_key + ", in subject " + key + \
                                  ", in category " + category + "!")
                            print("Falling back to linear interpolation...")
                    s = s.interpolate(method='linear', limit_direction='both')
                    sub_value["data"] = s.to_list()
                else:
                    if False not in nans:
                        if verbose:
                            print("Could not interpolate field " + sub_key + ", in subject " + key + \
                                  ", in category " + category + ", as all values were nans!")
                        if sanitize and sub_key != "":
                            sub_value["data"] = [0 for i in range(len(sub_value["data"]))]
                            if verbose:
                                print("Sanitizing field with all 0s...")
                            if category not in self._sanitized:
                                self._sanitized[category] = []
                            if key not in self._sanitized[category]:
                                self._sanitized[category].append(key)
                    if category not in self._nan_dict:
                        self._nan_dict[category] = {}
                    if key not in self._nan_dict[category]:
                        self._nan_dict[category][key] = {}
                    self._nan_dict[category][key][sub_key] = self._false_of_n(len(sub_value["data"]))

        return data

    ## Function to graph a certain field of data
    # @param category The category containing the data to be graphed
    # @param subject The subject containing the data to be graphed
    # @param field The field of the data to be graphed
    # @param showinterpolated Flag to set whether interpolated data should be graphed, defaults to True
    # @param colorinterpolated Flag to set whether interpolated data should be colored differently from normal data,
    # defaults to True
    # @param limits Configures the horizontal endpoints of the graph. A Tuple of the form `(start, end)`.
    def graph(self, category, subject, field, showinterpolated=True, colorinterpolated=True, limits=None):
        """Graphs the data specified. If showinterpolated is set to False, interpolated values will not be shown."""
        if not (category in self.data_dict and subject in self.data_dict[category] and field in
                self.data_dict[category][subject]):
            return  # We don't have any data for this field!
        interpolated = True in self._nan_dict[category][subject][field]
        if not interpolated or (not colorinterpolated and showinterpolated):  # Simplest case - just graph the data
            plt.plot(self.data_dict[category][subject][field]["data"])
            plt.xlabel("Frame")
            plt.ylabel(self.data_dict[category][subject][field]["unit"])
            plt.title("Data in category " + category + ", in subject " + subject + ", in field " + field)
            if limits is not None:
                plt.xlim(limits)
            plt.show()
        else:
            nans = self._nan_dict[category][subject][field]
            data = self.data_dict[category][subject][field]["data"]

            orgdatablocks = []
            interdatablocks = []
            orgtemp = []
            intertemp = []
            for i in range(len(nans)):
                if nans[i]:
                    if len(orgtemp) > 0:
                        orgdatablocks.append(orgtemp)
                        orgtemp = []
                    intertemp.append(i)
                else:
                    if len(intertemp) > 0:
                        interdatablocks.append(intertemp)
                        intertemp = []
                    orgtemp.append(i)
            if len(orgtemp) > 0:
                orgdatablocks.append(orgtemp)
            if len(intertemp) > 0:
                interdatablocks.append(intertemp)

            flagorg = True
            for blk in orgdatablocks:
                if flagorg:
                    plt.plot(blk, data[blk[0]:blk[len(blk) - 1] + 1], "C0", label="Original Data")
                    flagorg = False
                else:
                    plt.plot(blk, data[blk[0]:blk[len(blk) - 1] + 1], "C0")

            if showinterpolated:
                flagint = True
                for blk in interdatablocks:
                    if flagint:
                        plt.plot([blk[0]-1] + blk + [blk[len(blk) - 1] + 1], data[blk[0]-1:blk[len(blk) - 1] + 2], "C1", label="Interpolated Data")
                        flagint = False
                    else:
                        plt.plot([blk[0]-1] + blk + [blk[len(blk) - 1] + 1], data[blk[0]-1:blk[len(blk) - 1] + 2], "C1")
                plt.legend()

            plt.xlabel("Frame")
            plt.ylabel(self.data_dict[category][subject][field]["unit"])
            plt.title("Data in category " + category + ", in subject " + subject + ", in field " + field)
            if limits is not None:
                plt.xlim(limits)
            plt.show()

    def is_sanitized(self, category, subject):
        if category not in self._sanitized:
            return False
        for x in self._sanitized[category]:
            if subject in x:
                return True
        return False

    def _false_of_n(self, n):
        """Helper function to generate an array of Falses of length N"""
        arr = []
        for i in range(n):
            arr.append(False)
        return arr

    def _len_data(self, category):
        """Returns the length of the data section of a given category"""
        return len(next(next(self.data_dict[category].itervalues()).itervalues())["data"])

    def save(self, filename=None, verbose=False, mark_interpolated=True):
        file_path = self._file_path
        if filename is not None:
            file_path = filename
        if verbose and mark_interpolated:
            print("Saving data to " + file_path + ". Interpolated values will be marked with '!'.")
        if verbose and not mark_interpolated:
            print("Saving data to " + file_path + ". Interpolated values will not be marked.")
        with open(file_path, "wb") as f:
            f.seek(0)
            f.truncate()
            writer = csv.writer(f)
            for category, subjects in self.data_dict.items():  # for every category in the data...
                if verbose:
                    print("Saving category " + category + "...")
                #  write the header
                writer.writerow([category])
                if category == "Devices":
                    writer.writerow([1000])  # Devices section has 1000 (units??) framerate
                else:
                    writer.writerow([100])  # unlike all other sections, with 100 framerate
                # writer.writerow(["", ""])

                line = ["", ""]
                for subject, fields in subjects.iteritems():  # for every subject...
                    line.append(subject)
                    if len(fields) > 1:  # if the subject has at least two fields...
                        for i in range(len(fields) - 1):
                            line.append("")  # add empty space between subject names to make room for fields
                writer.writerow(line)

                line = ["Frame", "Sub Frame"]
                for subject, fields in subjects.iteritems():
                    for field, f_vals in fields.iteritems():
                        line.append(field)  # add name of each field
                writer.writerow(line)

                line = ["", ""]
                for subject, fields in subjects.iteritems():
                    for field, f_vals in fields.iteritems():
                        line.append(f_vals["unit"])  # add unit for each field
                writer.writerow(line)

                #  Time to write the data!
                for i in range(self._len_data(category)):
                    if category == "Devices":
                        frame = (i / 10) + 1
                        sub = i % 10
                    else:
                        frame = i + 1
                        sub = 0
                    line = [frame, sub]

                    for subject, fields in subjects.iteritems():
                        for field, f_vals in fields.iteritems():
                            x = f_vals["data"][i]
                            if mark_interpolated and self._nan_dict[category][subject][field][i]:
                                x = "!" + str(x)
                            elif np.isnan(x):
                                x = ""
                            line.append(x)
                    writer.writerow(line)
                writer.writerow(["", ""])
        if verbose:
            print("Saved!")

    def __eq__(self, other):
        try:
            return self.data_dict == other.data_dict
        except:
            return False

    def find_ineq(self, other):
        """
        Method to help find differences between different Vicon objects.
        """
        print("Scanning data for differences...")
        flag = False
        for category, subjects in self.data_dict.items():
            if category not in other.data_dict:
                print("Category " + category + " missing!")
                flag = True
            for subject, fields in subjects.items():
                if subject not in other.data_dict[category]:
                    print("Subject " + subject + " in category " + category + " missing!")
                    flag = True
                for field, f_vals in fields.items():
                    if field not in other.data_dict[category][subject]:
                        flag = True
                        print("Field " + field + " of subject " + subject + " in category " + category + " missing!")
                    elif len(f_vals["data"]) != len(other.data_dict[category][subject][field]["data"]):
                        flag = True
                        print("Data length mismatch in field " + field \
                              + " of subject " + subject + " in category " + category + "!")
                    elif set(f_vals["data"]) != set(other.data_dict[category][subject][field]["data"]):
                        flag = True
                        print("Data mismatch in field " + field \
                              + " of subject " + subject + " in category " + category + "!")
                    elif f_vals["data"] != other.data_dict[category][subject][field]["data"]:
                        flag = True
                        print("Data order mismatch in field " + field \
                              + " of subject " + subject + " in category " + category + "!")

                    if field in other.data_dict[category][subject] and f_vals["unit"] != \
                            other.data_dict[category][subject][field]["unit"]:
                        flag = True
                        print("Unit mismatch in field " + field \
                              + " of subject " + subject + " in category " + category + "!")
        if not flag:
            print("No differences detected!")


if __name__ == '__main__':
    file = "/home/nathaniel/AIM_GaitData/Gaiting_stairs/subject_08/subject_08_walking_01.csv"
    data = ViconOld(file)