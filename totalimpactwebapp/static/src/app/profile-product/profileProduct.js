angular.module("profileProduct", [
    'resources.users',
    'resources.products',
    'profileAward.profileAward',
    'services.page',
    'profile',
    'services.loading',
    'ui.bootstrap',
    'angularFileUpload',
    'pdf',
    'security'
  ])



  .config(['$routeProvider', function ($routeProvider) {

    $routeProvider.when("/:url_slug/product/:tiid", {
      templateUrl:'profile-product/profile-product-page.tpl.html',
      controller:'ProfileProductPageCtrl'
    });

  }])

  .factory('ProfileProduct', function(){
    return {

    }
  })

  .controller('ProfileProductPageCtrl', function (
    $scope,
    $routeParams,
    $location,
    $modal,
    $cacheFactory,
    $compile,
    $sce,
    security,
    UsersProduct,
    UsersProducts,
    UserProfile,
    Product,
    Loading,
    TiMixpanel,
    Page) {

    var slug = $routeParams.url_slug
    window.scrollTo(0,0)  // hack. not sure why this is needed.


    Loading.start('profileProduct')
    UserProfile.useCache(true)

    $scope.userSlug = slug
    $scope.loading = Loading
//    $scope.userOwnsThisProfile = security.testUserAuthenticationLevel("ownsThisProfile")
//    $scope.userOwnsThisProfile = false

    security.isLoggedInPromise(slug).then(
      function(resp){
        $scope.userOwnsThisProfile = true
      },
      function(resp){
        $scope.userOwnsThisProfile = false
      }
    )

    $scope.openInfoModal = function(){
      $modal.open({templateUrl: "profile-product/percentilesInfoModal.tpl.html"})
    }

    $scope.openFulltextLocationModal = function(){
      UserProfile.useCache(false)
      $modal.open(
        {templateUrl: "profile-product/fulltext-location-modal.tpl.html"}
        // controller specified in the template :/
      )
      .result.then(function(resp){
          console.log("closed the free fulltext modal; re-rendering product", resp)
          TiMixpanel.track("added free fulltext url",{
            url: resp.product.biblio.free_fulltext_url
          })
          renderProduct()
      })
    }

    $scope.deleteProduct = function(){
      Loading.start("deleteProduct")
      UserProfile.useCache(false)

      Product.delete(
        {user_id: slug, tiid: $routeParams.tiid},
        function(){
          Loading.finish("deleteProduct")
          TiMixpanel.track("delete product")
          security.redirectToProfile()
        }
      )
    }


    $scope.editProduct = function(){
      UserProfile.useCache(false)
      $modal.open({
        templateUrl: "profile-product/edit-product-modal.tpl.html",
        controller: "editProductModalCtrl",
        resolve: {
          product: function(){
            return $scope.product
          }
        }
      })
      .result.then(
        function(resp){
          console.log("closed the editProduct modal; re-rendering product")
          renderProduct()
        }
      )
    }

    var renderProduct = function(){
      $scope.product = UsersProduct.get({
        id: $routeParams.url_slug,
        tiid: $routeParams.tiid
      },
      function(data){
        Loading.finish('profileProduct')
        Page.setTitle(data.biblio.title)
        $scope.productMarkup = data.markup
        console.log("loaded a product", data)
        window.scrollTo(0,0)  // hack. not sure why this is needed.


      },
      function(data){
        $location.path("/"+slug) // replace this with "product not found" message...
      }
      )
    }

    renderProduct()

  })


.controller("editProductModalCtrl", function($scope,
                                             $location,
                                             $modalInstance,
                                             $routeParams,
                                             Loading,
                                             product,
                                             UsersProduct,
                                             ProductBiblio){

    // this shares a lot of code with the freeFulltextUrlFormCtrl below...refactor.
    $scope.product = product
    var tiid = $location.path().match(/\/product\/(.+)$/)[1]
    $scope.onCancel = function(){
      $scope.$close()
    }

    $scope.onSave = function() {
      Loading.start("saveButton")
      console.log("saving...", tiid)
      ProductBiblio.patch(
        {'tiid': tiid},
        {
          title: $scope.product.biblio.title,
          authors: $scope.product.biblio.authors,
          journal: $scope.product.biblio.journal,
          year: $scope.product.biblio.year

        },
        function(resp){
          console.log("saved new product biblio", resp)
          Loading.finish("saveButton")
          console.log("got a response back from the UsersProduct.get() call", resp)
          return $scope.$close(resp)

        }
      )
    }
  })


.controller("freeFulltextUrlFormCtrl", function($scope,
                                                $location,
                                                Loading,
                                                TiMixpanel,
                                                ProductBiblio){
  var tiid = $location.path().match(/\/product\/(.+)$/)[1]

  $scope.free_fulltext_url = ""
  $scope.onSave = function() {
    Loading.start("saveButton")
    console.log("saving...", tiid)


    ProductBiblio.patch(
      {'tiid': tiid},
      {free_fulltext_url: $scope.free_fulltext_url},
      function(resp){
        Loading.finish("saveButton")
        return $scope.$close(resp)
      }
    )
  }
})



.controller("productUploadCtrl", function($scope, $upload){
    $scope.onFileSelect = function($files){
      console.log("trying to upload files", $files)

      $scope.upload = $upload.upload({
        url: "/product/123",
        file: $files[0]
      })
      .success(function(data){
        console.log("success on upload", data)
      })

    }
})


.controller("pdfCtrl", function($scope){
    $scope.pdfName = 'Relativity: The Special and General Theory by Albert Einstein';
    $scope.pdfUrl = 'http://localhost:5000/test-pdf';
    $scope.getNavStyle = function(scroll) {
      console.log(scroll)
      if(scroll < 150) return 'fixed';
    }
})



  .directive('dynamic', function ($compile) {
  return {
    restrict: 'A',
    replace: true,
    link: function (scope, ele, attrs) {
      scope.$watch(attrs.dynamic, function(html) {
        ele.html(html);
        $compile(ele.contents())(scope);
      });
    }
  };
});















