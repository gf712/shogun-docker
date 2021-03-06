FROM debian:stretch
MAINTAINER gf712

RUN apt-get update -qq && apt-get upgrade -y && \
    apt-get install -qq --force-yes --no-install-recommends make gcc g++ \
    libc6-dev libbz2-dev libjson-c-dev ccache libarpack2-dev libatlas-base-dev \
    libblas-dev libglpk-dev libhdf5-serial-dev zlib1g-dev liblapacke-dev cmake \
    libnlopt-dev liblpsolve55-dev libxml2-dev libsnappy-dev liblzo2-dev \
    liblzma-dev libeigen3-dev swig3.0 python-dev python-numpy python-matplotlib python-scipy \
    python-jinja2 python-setuptools git-core wget jblas mono-devel mono-dmcs cli-common-dev \
    lua5.1 liblua5.1-0-dev octave liboctave-dev r-base-core clang \
    openjdk-8-jdk ruby ruby-dev python-ply sphinx-doc python-pip \
    exuberant-ctags clang-format-3.8 libcereal-dev libcolpack-dev lcov \
    protobuf-compiler libprotobuf-dev scala googletest gnupg dirmngr valgrind

RUN apt-key adv --recv-keys --keyserver keyserver.ubuntu.com 8A9CA30DB3C431E3
RUN echo "deb http://ppa.launchpad.net/timsc/swig-3.0.12/ubuntu xenial main" | tee -a /etc/apt/sources.list
RUN apt-get update -qq && apt-get upgrade -y

RUN pip install sphinx ply sphinxcontrib-bibtex sphinx_bootstrap_theme codecov
RUN gem install narray
RUN cd /usr/bin && ln -s swig3.0 swig && ln -s ccache-swig3.0 ccache-swig

ADD http://crd.lbl.gov/~dhbailey/mpdist/arprec-2.2.19.tar.gz /tmp/
RUN cd /tmp && \
    tar zxpf arprec-2.2.19.tar.gz && \
    cd arprec && ./configure --enable-shared && \
    make install && ldconfig

ADD http://dl.bintray.com/sbt/debian/sbt-0.13.6.deb /tmp/sbt.deb
RUN dpkg -i /tmp/sbt.deb

ADD https://github.com/ReactiveX/RxCpp/archive/4.1.0.tar.gz /tmp/
RUN cd /tmp;\
    tar -xvf 4.1.0.tar.gz;\
    cd RxCpp-4.1.0/projects/;\
    mkdir build;\
    cd build;\
    cmake ../../;\
    make install;

ADD https://github.com/shogun-toolbox/tflogger/archive/v0.1.1.tar.gz /tmp/
RUN cd /tmp;\
    tar -xvf v0.1.1.tar.gz;\
    cd tflogger-0.1.1;\
    mkdir build;\
    cd build;\
    cmake ../;\
    make install;
