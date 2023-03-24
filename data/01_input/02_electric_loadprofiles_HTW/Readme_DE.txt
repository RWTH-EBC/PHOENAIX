## Der hier abliegende Datensatz wurde aus dem unten beschriebenen Datensatz extrahiert und ist in UTC gegeben.





##Erklärung des Datensatzes unter:
http://dx.doi.org/10.13140/RG.2.1.5112.0080/1

##Zitation:
Tjaden, T.; Bergner, J.; Weniger, J.; Quaschning, V.: „Repräsentative elektrische Lastprofile für Einfamilienhäuser in Deutschland auf 1-sekündiger Datenbasis“, Datensatz, Hochschule für Technik und Wirtschaft (HTW) Berlin, Lizenz: CC-BY-NC-4.0, heruntergeladen am [Datum].

##Inhalt des Datensatzes
PL1					-> Matrize [31536000/525600x74] -> ein Jahr Wirkleistung Phase L1 in W in sekündlicher ["_1s_"] / minütlicher ["_1min_"] Auflösung, Spalte entspricht Nr. des Lastprofils
PL2					-> Matrize [31536000/525600x74] -> ein Jahr Wirkleistung Phase L2 in W in sekündlicher ["_1s_"] / minütlicher ["_1min_"] Auflösung, Spalte entspricht Nr. des Lastprofils
PL3					-> Matrize [31536000/525600x74] -> ein Jahr Wirkleistung Phase L3 in W in sekündlicher ["_1s_"] / minütlicher ["_1min_"] Auflösung, Spalte entspricht Nr. des Lastprofils
QL1					-> Matrize [31536000/525600x74] -> ein Jahr Blindleistung Phase L1 in W in sekündlicher ["_1s_"] / minütlicher ["_1min_"] Auflösung, Spalte entspricht Nr. des Lastprofils
QL2					-> Matrize [31536000/525600x74] -> ein Jahr Blindleistung Phase L2 in W in sekündlicher ["_1s_"] / minütlicher ["_1min_"] Auflösung, Spalte entspricht Nr. des Lastprofils
QL3					-> Matrize [31536000/525600x74] -> ein Jahr Blindleistung Phase L3 in W in sekündlicher ["_1s_"] / minütlicher ["_1min_"] Auflösung, Spalte entspricht Nr. des Lastprofils
												(postive Blindleistung ist induktiv, negative Blindleistung ist kapazitiv)
time_datenum_MEZ 	-> Matrize [31536000/525600x1]  -> Zeitstempel in lokaler Winterzeit (MEZ) im Matlabformat http://de.mathworks.com/help/matlab/ref/datenum.html
time_datevec_MEZ	-> Matrize [31536000/525600x6]  -> Zeitstempel in lokaler Winterzeit (MEZ)
								Spalte 1 = Jahr
								Spalte 2 = Monat des Jahres 	[1..12]
								Spalte 3 = Tag des Monats 		[1..31]
								Spalte 4 = Stunde des Tages 	[0..23]
								Spalte 5 = Minute der Stunde 	[0..59]
								Spalte 6 = Sekunde der Minute 	[0..59]
##Speicherplatz
["_1s_"]
Matlab-Datei (*.mat) = 4,08 GB
CSV-Datei (*.csv) = 5,44 GB gepackt und ca. 45 GB entpackt.
["_1min_"]
Matlab-Datei (*.mat) = 0,17 GB
CSV-Datei (*.csv) = 0,21 GB gepackt und ca. 0,7 GB entpackt.

##Publikationen
Puplikationen die den Datensatz verwendet haben finden Sie unter anderem unter
https://pvspeicher.htw-berlin.de
