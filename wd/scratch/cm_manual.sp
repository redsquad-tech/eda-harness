* Current Mirror DC Sweep
* Generated manually for ngspice

.lib "/mnt/storage/work/polin-agent/pdks/volare/sky130/versions/0fe599b2afb6708d281543108caf8310912f54af/sky130A/libs.tech/ngspice/sky130.lib.spice" tt

.option reltol = 0.00001

* Current Mirror DUT
xmref
+ ibias ibias 0 0 
+ sky130_fd_pr__nfet_01v8
+ w='2' l='0.15' nf='4' ad='int((nf+1)/2) * w/nf * 0.29' As='int((nf+2)/2) * w/nf * 0.29' pd='2*int((nf+1)/2) * (w/nf + 0.29)' ps='2*int((nf+2)/2) * (w/nf + 0.29)' nrd='0.29 / w' nrs='0.29 / w' sa='0' sb='0' sd='0' mult='1' m='1' 

xmout
+ iout ibias 0 0 
+ sky130_fd_pr__nfet_01v8
+ w='2' l='0.15' nf='4' ad='int((nf+1)/2) * w/nf * 0.29' As='int((nf+2)/2) * w/nf * 0.29' pd='2*int((nf+1)/2) * (w/nf + 0.29)' ps='2*int((nf+2)/2) * (w/nf + 0.29)' nrd='0.29 / w' nrs='0.29 / w' sa='0' sb='0' sd='0' mult='1' m='1' 

* Bias current source
iiref
+ ibias 0 
+ 10u

* Output voltage source for DC sweep
vvoutsrc
+ iout 0 
+ dc 0.9

* DC sweep
.dc vvoutsrc 0 1.8 0.01

* Save currents and voltages
.save i(vvoutsrc) v(iout) v(ibias)

.end
