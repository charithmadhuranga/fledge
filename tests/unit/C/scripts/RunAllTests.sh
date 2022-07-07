#!/bin/sh
#set -e
#
# This is the shell script wrapper for running C unit tests
#
jobs="-j4"
if [ "$1" = "-j*" ]; then
  jobs="$1"
fi

COVERAGE=0
if [ "$1" = "coverage" ]; then
  COVERAGE=1
fi

if [ "$FLEDGE_ROOT" = "" ]; then
	echo You must set FLEDGE_ROOT before running this script
	exit -1
fi
exitstate=0

cd $FLEDGE_ROOT/tests/unit/C
if [ ! -d results ] ; then
	mkdir results
fi

if [ -f "./CMakeLists.txt" ] ; then
	echo -n "Compiling libraries..."
	(rm -rf build && mkdir -p build && cd build && cmake -DCMAKE_BUILD_TYPE=Debug .. && make ${jobs} && cd ..) > /dev/null
	echo "done"
fi

cmakefile=`find . -name CMakeLists.txt | grep -v "\.\/CMakeLists.txt" `
for f in $cmakefile; do	
	echo "-----------------> Processing $f <-----------------"
	dir=`dirname $f`
	echo Testing $dir
	(
		cd $dir;
		rm -rf build;
		mkdir build;
		cd build;
		echo Building Tests...;
		cmake -DCMAKE_BUILD_TYPE=Debug ..;
		rc=$?
		if [ $rc != 0 ]; then
			echo cmake failed for $dir;
			exit 1
		fi
		make ${jobs} > /dev/null;
		rc=$?
		if [ $rc != 0 ]; then
			echo make failed for $dir;
			exit 1
		fi
		if [ $COVERAGE -eq 0 ]; then
			echo Running tests...;
			if [ -f "./RunTests" ] ; then
				./RunTests --gtest_output=xml > /tmp/results;
				rc=$?
				if [ $rc != 0 ]; then
					exit $rc
				fi
			fi
		fi

		if [ $COVERAGE -eq 1 ]; then
			echo Generating coverage reports...;
			file=$(basename $f)
			# echo "pwd=`pwd`, f=$f, file=$file"
			grep -q CoverageHtml ../${file}
			[ $? -eq 0 ] && (echo Running "make CoverageHtml" && make CoverageHtml) || echo "CoverageHtml target not found, skipping..."
		fi

	) >/dev/null
	rc=$?
	if [ $rc != 0 ]; then
		echo Tests for $dir failed
		cat /tmp/results
		exitstate=1
	else
		echo All tests in $dir passed
	fi
	file=`echo $dir | sed -e 's#./##' -e 's#/#_#g'`
	source_file=$dir/build/test_detail.xml
	if [ -f "$source_file" ] ; then
		mv $source_file results/${file}.xml
	fi
done
exit $exitstate
