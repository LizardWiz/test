import subprocess

#def runcmd(cmd, verbose = False, *args, **kwargs):
#
#    process = subprocess.Popen(
#        cmd,
#        stdout = subprocess.PIPE,
##        stderr = subprocess.PIPE,
 #       text = True,
 #       shell = True
 #   )
 #   std_out, std_err = process.communicate()
 #   if verbose:
 #       print(std_out.strip(), std_err)
 #   pass

print("jello world")
print("jelly world")

#child = subprocess.Popen(['wget','https://mega.nz/folder/DfBWGTjA#BFcNX-XcMEnY-cdFDWTx1Q/file/WO43iKLZ'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
child = subprocess.Popen(['wget','https://mega.nz/folder/DfBWGTjA#BFcNX-XcMEnY-cdFDWTx1Q'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

print(child.stdout.read())
#runcmd('wget "https://mega.nz/folder/DfBWGTjA#BFcNX-XcMEnY-cdFDWTx1Q/file/WO43iKLZ"')