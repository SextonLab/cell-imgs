import os
import sys
import glob
import json

import numpy as np
import pandas as pd

import tifffile as tif

from cellimgs.scripts import generate_masks
from cellpose import models, utils

from datetime import date

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtWidgets import QFileDialog
from PyQt6 import uic



class MainWindow(QtWidgets.QMainWindow):

    def __init__(self) -> None:
        super().__init__()
        uic.loadUi(os.path.join("gui", "genMask.ui"), self)
        self.imgDir = ""
        self.maskDir = ""

        # load/save dictionary
        self.params = {
            "date":date.today().strftime("%Y-%m-%d"),
            "img_dir": self.imgLabel.text(),
            "mask_dir": self.maskLabel.text(),
            "model": str(self.modBox.currentText()),
            "channel":self.chanLine.text(),
            "diam":self.diamSpin.value(),
            "flow":self.flowSpin.value(),
            "prob":self.probSpin.value(),
            "edge":self.edgeCheck.isChecked(),
            "replace":self.replace.isChecked(),
            "count":self.countBox.isChecked()
        }

        # Top Menu
        self.actionQuit.triggered.connect(self.close)
        self.actionSave.triggered.connect(self.save)
        self.actionLoad.triggered.connect(self.load)

        # Buttons
        self.imgBtn.clicked.connect(self.load_images)
        self.maskBtn.clicked.connect(self.load_masks)
        self.genMaskBtn.clicked.connect(self.gen_masks)
    
    # Directory button actions
    def load_images(self):
        self.imgDir = QtWidgets.QFileDialog.getExistingDirectory(self, 'Select Image Folder')
        self.imgLabel.setText(self.imgDir)
    
    def load_masks(self):
        self.maskDir = QtWidgets.QFileDialog.getExistingDirectory(self, 'Select Mask Folder')
        self.maskLabel.setText(self.maskDir)
    
    def update_params(self):
        mods = ['cyto','nuclei','tissuenet','livecell', 'cyto2', 'general',
                'CP', 'CPx', 'TN1', 'TN2', 'TN3', 'LC1', 'LC2', 'LC3', 'LC4']

        # [ 'img_dir', 'mask_dir', 'model', 'channel', 'diam', 'flow', 'prob', 'edge', 'replace', 'count']
        self.imgLabel.setText(self.params['img_dir'])
        self.maskLabel.setText(self.params['mask_dir'])
        self.modBox.setCurrentIndex(mods.index(self.params['model']))
        self.chanLine.setText(self.params['channel'])
        self.diamSpin.setValue(self.params['diam'])
        self.flowSpin.setValue(self.params['flow'])
        self.probSpin.setValue(self.params['prob'])
        self.edgeCheck.setChecked(self.params['edge'])
        self.replace.setChecked(self.params['replace'])
        self.countBox.setChecked(self.params['count'])

    # Drop down menu actions
    def load(self):
        print("loading")
        fname, _ = QFileDialog.getOpenFileName(
            self,
            "Open settings file",
            "${HOME}",
            "JSON Files (*.json)"
            )
        with open(fname) as f:
            self.params = json.load(f)
        self.update_params()
        
    
    def save(self):
        print('saving')
        self.params = {
            "date":date.today().strftime("%Y-%m-%d"),
            "img_dir": self.imgLabel.text(),
            "mask_dir": self.maskLabel.text(),
            "model": str(self.modBox.currentText()),
            "channel":self.chanLine.text(),
            "diam":self.diamSpin.value(),
            "flow":self.flowSpin.value(),
            "prob":self.probSpin.value(),
            "edge":self.edgeCheck.isChecked(),
            "replace":self.replace.isChecked(),
            "count":self.countBox.isChecked()
        }
        fname, _ = QFileDialog.getSaveFileName(
            self,
            "Save settings file",
            "${HOME}/settings.json",
            "JSON Files (*.json)"
            )
        with open(fname, 'w') as f:
            json.dump(self.params, f)

    def gen_masks(self):
        self.update()
        print("Generating Masks")
        if not os.path.exists(os.path.join(self.maskDir, 'count.csv')):
            csv_path = os.path.join(self.maskDir, 'count.csv')
            cell_count = {"image":[], "count":[]}
        exten1 = os.path.join(self.imgLabel.text(), f"*{self.chanLine.text()}.tif")
        exten2 = os.path.join(self.imgLabel.text(), f"*{self.chanLine.text()}.tiff")
        files = glob.glob(exten1)+glob.glob(exten2)
        model = models.CellposeModel(model_type=self.modBox.currentText(), gpu=True)
        
        nimg = len(files)
        assert nimg > 0, "No Images Found"

        channel = [[0,0]]
        diam = self.diamSpin.value()
        if diam == 0:
            diam = None
        
        names = [f.split(os.sep)[-1] for f in files]
        for i, f in enumerate(files):
            fname = os.path.join(self.maskLabel.text(),names[i])
            if not os.path.exists(fname) or self.replace.isChecked():
                img = tif.imread(f)
                print(f'Processing Image: {i+1} of {len(names)}')
                mask, _, _ = model.eval(
                    img, 
                    diameter=self.diamSpin.value(), 
                    channels=channel, 
                    flow_threshold=self.flowSpin.value(), 
                    cellprob_threshold=self.probSpin.value()
                    ) # , do_3d=do_3d

                if self.edgeCheck.isChecked():
                    mask = utils.remove_edge_masks(mask)
                tif.imsave(fname, mask.astype('uint16'))
                if self.countBox.isChecked():
                    cell_count['image'].append(f)
                    cell_count['count'].append(len(utils.outlines_list(mask)))
                del mask
            else:
                print(f'Skipping Image: {i+1} of {len(names)} [Already exists]')
            self.progressBar.setValue(int(((i+1)/nimg)*100))
        
        if self.countBox.isChecked():
            pd.DataFrame(data=cell_count).to_csv(csv_path, index=False)





def main():
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    app.exec()

if __name__ =='__main__':
    main()